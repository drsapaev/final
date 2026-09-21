"""Codex R1 #3092 (P1) — distributed Idempotency-Key claim.

Original defect: IdempotencyMiddleware used a per-process in-memory cache that
records a key only AFTER the handler completes. Staging runs two backend
workers (ops/compose.staging.yml), so a lost response retried on another
worker — or a retry overlapping the first request — re-executed
/registrar/cart and created duplicate visits/invoices despite the reused key.

Contract now (when Redis is reachable — simulated here with a fake client):
  1. A retry that lands on another worker replays the stored 2xx response;
     the handler executed exactly ONCE.
  2. A retry overlapping an in-flight request receives 409 Conflict instead
     of executing the handler a second time.
  3. Non-2xx responses release the claim — retry with the same key re-runs.
  4. Redis unavailable → per-process in-memory fallback (original PR-6
     behavior), traffic never breaks.

Codex R2 #3092 additions:
  5. A retry with the SAME key and a CHANGED body gets 409, never the
     original success replayed over different data (payload-hash binding).
  6. The in-flight claim uses a SHORT renewable lease, not the 24h TTL.
  7. A transient Redis failure degrades, then RECOVERS (re-probe) instead
     of permanently disabling coordination on the worker.
  8. The Redis URL is redacted before logging (credentials never reach logs).

Codex R3 #3092 additions:
  9. The cache namespace comes from a VERIFIED bearer JWT; requests without
     a verifiable identity bypass idempotency entirely (nothing stored,
     nothing replayed) — no more user-0 shared namespace.
 10. Cross-principal replay is impossible: two verified principals sharing
     one key never see each other's cached response; a principal that fails
     the DB authorization check (revoked/deactivated) gets no replay.
 11. Lease renewal/release are bound to the owner token (compare-and-expire
     / compare-and-delete) — a stale worker can neither extend nor delete a
     replacement claim acquired by another worker.
"""
from __future__ import annotations

import json
import threading
import uuid
from typing import Any

import pytest
from fastapi import Depends, FastAPI, Request
from fastapi.testclient import TestClient

from app.middleware import idempotency_middleware as idem_module
from app.middleware.idempotency_middleware import (
    DistributedIdempotencyClaim,
    IdempotencyMiddleware,
)


class FakeRedis:
    """Minimal Redis subset: SET NX/XX EX / GET / DEL / PING — shared across
    'workers' to emulate the staging deployment. Tracks per-key TTLs."""

    def __init__(self) -> None:
        self.store: dict[str, str] = {}
        self.ttls: dict[str, int | None] = {}
        self.fail_next_ops = 0

    def ping(self) -> bool:
        if self.fail_next_ops > 0:
            self.fail_next_ops -= 1
            raise ConnectionError("simulated transient redis failure")
        return True

    def set(
        self,
        key: str,
        value: str,
        nx: bool = False,
        xx: bool = False,
        ex: int | None = None,
    ) -> bool | None:
        if self.fail_next_ops > 0:
            self.fail_next_ops -= 1
            raise ConnectionError("simulated transient redis failure")
        if nx and key in self.store:
            return None
        if xx and key not in self.store:
            return None
        self.store[key] = value
        self.ttls[key] = ex
        return True

    def get(self, key: str) -> str | None:
        if self.fail_next_ops > 0:
            self.fail_next_ops -= 1
            raise ConnectionError("simulated transient redis failure")
        return self.store.get(key)

    def delete(self, key: str) -> int:
        if self.fail_next_ops > 0:
            self.fail_next_ops -= 1
            raise ConnectionError("simulated transient redis failure")
        return 1 if self.store.pop(key, None) is not None else 0

    def exists(self, key: str) -> int:
        """Codex R9 #3092: EXISTS probe for the execution-intent marker."""
        if self.fail_next_ops > 0:
            self.fail_next_ops -= 1
            raise ConnectionError("simulated transient redis failure")
        return 1 if key in self.store else 0

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        """Emulate the Lua compare-and-* scripts used by the claim.

        Round-8: multi-key eval (the atomic response+scope store) and the
        scope-binding upsert are emulated by their embedded marker comments;
        the compare-and-delete scripts (intent release, scope CAS delete)
        share the same ``get == ARGV[1] → del`` shape and the del branch."""
        if self.fail_next_ops > 0:
            self.fail_next_ops -= 1
            raise ConnectionError("simulated transient redis failure")
        keys = list(keys_and_args[:numkeys])
        args = list(keys_and_args[numkeys:])
        if numkeys == 2 and "store+scope" in script:
            # -- store+scope: response SET + value-guarded binding
            # restore/refresh in ONE script. Return 2 when the binding holds
            # a foreign scope (the response is stored, the binding is not).
            resp_key, scope_key = keys
            snapshot, ttl, expected_scope, new_value = args
            self.store[resp_key] = snapshot
            self.ttls[resp_key] = int(ttl)
            existing = self.store.get(scope_key)
            if existing is not None:
                scope, sep, _gen = existing.partition("|")
                if scope != expected_scope or sep != "|":
                    return 2
            self.store[scope_key] = new_value
            self.ttls[scope_key] = int(ttl)
            return 1
        if numkeys == 2:
            claim_key, intent_key = keys
            token, ttl = args
            if self.store.get(claim_key) != token:
                return -1
            existing = self.store.get(intent_key)
            if existing is not None and existing != token:
                return -2
            # Preserve the existing transport-failure injection seam. The
            # real Lua operation is separately exercised against Redis below.
            self.set(intent_key, token, ex=int(ttl))
            return 1
        if "scope-upsert" in script:
            # -- scope-upsert: value-guarded restore-or-refresh of the
            # "<scope>|<generation>" binding value.
            key = keys[0]
            expected_scope, new_value, ttl = args
            existing = self.store.get(key)
            if existing is not None:
                scope, sep, _gen = existing.partition("|")
                if scope != expected_scope or sep != "|":
                    return 0
            self.store[key] = new_value
            self.ttls[key] = int(ttl)
            return 1
        if "del" in script:
            key = keys[0]
            if self.store.get(key) == args[0]:
                self.store.pop(key)
                self.ttls.pop(key, None)
                return 1
            return 0
        if "expire" in script:
            key = keys[0]
            if self.store.get(key) == args[0]:
                self.ttls[key] = int(args[1])
                return 1
            return 0
        raise AssertionError(f"unexpected Lua script: {script}")


def auth_headers(sub: str = "1") -> dict[str, str]:
    """Bearer token for a verified principal (Codex R3 #3092 P1)."""
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(sub)}"}


def nkey(sub: str, key: str, kind: str, path: str = "/echo") -> str:
    """Redis key under the hashed CANONICAL namespace of the given principal
    (Codex R11 #3092: the harness stubs resolve sub "1"/"2" to user 1/2).
    Round-3 (owner P2): the namespace binds the OPERATION — method + path —
    so harness keys are computed with the same scope the dispatch uses."""
    ns = IdempotencyMiddleware._namespace(int(sub), f"POST:{path}")
    return f"idem:{ns}:{key}:{kind}"


def _make_claim(fake: FakeRedis) -> DistributedIdempotencyClaim:
    """Build a claim instance without a real Redis (bypass from_url/ping)."""
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._prefix = "idem"
    claim._client = fake
    claim._available = True
    # The harness Redis is "up from boot": bindings may exist only in Redis
    # (round-5 owner P1 — the degraded-path decision reads this flag).
    claim._ever_available = True
    return claim


def _policy_dep() -> None:
    """Stand-in for require_roles(...) — a dependency that carries the
    published RBAC policy the idempotency middleware reads at replay time
    (the SSOT require_roles attaches `required_roles` to its _dep)."""
    return None


_policy_dep.required_roles = ("Admin", "Registrar")


def _make_app(counter: dict, call_next_error: Exception | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/echo")
    async def _echo() -> dict[str, Any]:
        counter["calls"] += 1
        return {"ok": True, "calls": counter["calls"]}

    @app.post("/cart-like")
    async def _cart_like(_policy: None = Depends(_policy_dep)) -> dict[str, Any]:
        # /registrar/cart accepts BOTH Admin and Registrar (_cart.py:14-18)
        counter["calls"] += 1
        return {"ok": True, "calls": counter["calls"]}

    @app.post("/inline-auth")
    async def _inline_auth() -> Any:
        # Codex R12 #3092 (P1): mirror of queue.py:533-606 — authorization
        # enforced INSIDE the handler (no require_roles dependency):
        # get_current_user + staff_authorization_service.can_read_queue() +
        # a doctor-ownership check decide whether patient_name is exposed.
        from fastapi.responses import JSONResponse

        counter["inline"]["calls"] += 1
        if not counter["inline"]["allowed"]:
            return JSONResponse(status_code=403, content={"detail": "inline authz refused"})
        return {"ok": True, "patient_name": "Тестовый Пациент"}

    @app.post("/boom")
    async def _boom() -> dict[str, str]:
        counter["calls"] += 1
        raise RuntimeError("simulated handler crash")

    @app.post("/bad")
    async def _bad() -> Any:
        # Returns (does not raise) a non-2xx: the endpoint completed its
        # validation without committing — outcome KNOWN.
        from fastapi.responses import JSONResponse

        counter["calls"] += 1
        return JSONResponse(status_code=400, content={"detail": "validation failed"})

    return app


@pytest.fixture
def fake_redis() -> FakeRedis:
    return FakeRedis()


@pytest.fixture
def two_workers(fake_redis: FakeRedis):
    """Two TestClients (simulated workers) sharing one Redis; both middlewares
    see the same distributed claim, while per-process caches stay separate.
    Codex R3: the DB authorization check is stubbed AUTHORIZED by default —
    dedicated tests below flip it to pin the fail-closed behavior."""
    # Reset the module-level distributed singleton and wire the fake
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    idem_module._distributed_claim = _make_claim(fake_redis)
    # Round-9: the deployment-wide bridge anchor cache must not leak
    # between tests (each test's fake store anchors its own window).
    saved_anchor_cache = idem_module._BRIDGE_ANCHOR_CACHE
    idem_module._BRIDGE_ANCHOR_CACHE = (False, 0.0)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    # Codex R11 #3092: the canonical resolution is stubbed — numeric subs are
    # user ids as-is; username subjects get a stable synthetic id (same
    # username -> same namespace within the harness run).
    subject_ids: dict[str, int] = {}

    def _harness_resolve(request, user_id, username):
        if user_id is not None:
            return user_id
        if not username:
            return None
        return subject_ids.setdefault(username, 9000 + len(subject_ids) + 1)
    idem_module._resolve_principal_id_sync = _harness_resolve

    counters = {"w1": {"calls": 0, "inline": {"calls": 0, "allowed": True}}, "w2": {"calls": 0, "inline": {"calls": 0, "allowed": True}}}
    client1 = TestClient(_make_app(counters["w1"]), raise_server_exceptions=False)
    client2 = TestClient(_make_app(counters["w2"]), raise_server_exceptions=False)
    yield client1, client2, counters, fake_redis

    idem_module._distributed_claim = saved
    idem_module._check_principal_authorized_sync = saved_auth
    idem_module._patient_replay_policy_sync = saved_patient_policy
    idem_module._BRIDGE_ANCHOR_CACHE = saved_anchor_cache
    idem_module._resolve_principal_id_sync = saved_resolve


def test_retry_on_other_worker_replays_response_executes_once(two_workers):
    """Lost response → retry hits ANOTHER worker → replay, handler ran once."""
    client1, client2, counters, _ = two_workers
    headers = {**auth_headers("1"), "Idempotency-Key": "codex-r1-lost-response"}

    first = client1.post("/echo", headers=headers)
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # Retry lands on worker 2 (different process cache — cold)
    second = client2.post("/echo", headers=headers)
    assert second.status_code == 200
    assert second.json()["ok"] is True
    # Handler did NOT run again on either worker
    assert counters["w1"]["calls"] == 1
    assert counters["w2"]["calls"] == 0


def test_in_flight_overlap_returns_409_not_second_execution(two_workers):
    """Overlapping retry while worker 1 is still in flight → 409 Conflict,
    handler never re-executes (previously: duplicate cart)."""
    client1, client2, counters, fake_redis = two_workers

    # Simulate worker 1 holding an in-flight claim (handler not finished yet)
    claim_key = nkey("1", "overlap-key", "claim")
    fake_redis.store[claim_key] = uuid.uuid4().hex

    response = client2.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "overlap-key"})
    assert response.status_code == 409
    assert response.headers.get("Retry-After") == "1"
    assert counters["w2"]["calls"] == 0, (
        "overlapping retry must not execute the handler a second time"
    )


def test_in_flight_claim_replays_if_response_landed_between_attempts(two_workers):
    """Claim fails but response completes before the re-check → replay, 200."""
    client1, client2, counters, fake_redis = two_workers

    key = "race-key"
    h1 = auth_headers("1")
    # Worker 1 completes: snapshot stored, claim released
    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    # (worker 2's per-process cache is cold; only Redis knows the response)
    resp_snapshot_key = nkey("1", key, "resp")
    assert resp_snapshot_key in fake_redis.store

    # A claim is (re)acquired concurrently — then worker 2 retries:
    # acquire fails on the stale claim, but the re-check finds the snapshot.
    fake_redis.store[nkey("1", key, "claim")] = uuid.uuid4().hex
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 0


def test_handler_crash_keeps_intent_retry_reconciles_instead_of_rerunning(two_workers):
    """Codex R9 #3092 (P1): the crash may have happened AFTER the endpoint's
    commit — the outcome is unknown, so the retry reconciles (409) instead of
    blindly re-executing the write. The in-flight claim IS released (the
    refusal must not leave a stale lock); the intent marker survives so the
    key can never silently re-execute its way to a duplicate."""
    client1, client2, counters, fake_redis = two_workers

    first = client1.post("/boom", headers={**auth_headers("1"), "Idempotency-Key": "crash-key"})
    assert first.status_code == 500
    assert nkey("1", "crash-key", "claim", path="/boom") not in fake_redis.store, (
        "crashed handler must release the in-flight claim"
    )
    assert nkey("1", "crash-key", "intent", path="/boom") in fake_redis.store, (
        "the pre-execution intent marker survives the crash (unknown outcome)"
    )

    second = client2.post("/boom", headers={**auth_headers("1"), "Idempotency-Key": "crash-key"})
    assert second.status_code == 409
    assert counters["w1"]["calls"] == 1
    assert counters["w2"]["calls"] == 0, (
        "retry after an unknown-outcome crash must NOT re-execute the write"
    )


def test_returned_non_2xx_clears_intent_so_retry_reruns(two_workers):
    """A RETURNED error response means the endpoint completed without a
    commit — the outcome is known, so the intent marker is cleared and the
    documented retry-with-the-same-key contract keeps working."""
    client1, client2, counters, fake_redis = two_workers

    first = client1.post("/bad", headers={**auth_headers("1"), "Idempotency-Key": "bad-key"})
    assert first.status_code == 400
    assert nkey("1", "bad-key", "intent", path="/bad") not in fake_redis.store, (
        "a returned error clears the intent marker (outcome known: nothing applied)"
    )

    second = client2.post("/bad", headers={**auth_headers("1"), "Idempotency-Key": "bad-key"})
    assert second.status_code == 400
    assert counters["w1"]["calls"] == 1
    assert counters["w2"]["calls"] == 1, (
        "retry after a known-outcome failure re-executes (errors are not cached)"
    )


def test_lost_outcome_retry_refused_then_replays_once_response_lands(two_workers):
    """The 90-second lost-response window: a previous attempt marked the
    execution intent and died before storing the outcome. The retry is
    refused with 409 (uncertain), never re-executed; once the response IS
    stored, the same key replays it normally."""
    client1, client2, counters, fake_redis = two_workers

    # A previous attempt reached execution on worker 1 and died right after
    # the marker (no stored response) — simulated directly:
    claim = idem_module._distributed_claim
    claim.mark_execution_intent(
        idem_module.IdempotencyMiddleware._namespace(1, "POST:/echo"), "lost-key"
    )

    retry = client2.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "lost-key"})
    assert retry.status_code == 409
    assert counters["w2"]["calls"] == 0, "no blind re-execution over an unknown outcome"

    # The outcome lands (e.g. the outcome was actually stored by recovery):
    from fastapi import Response as FastAPIResponse

    claim.store_response(
        idem_module.IdempotencyMiddleware._namespace(1, "POST:/echo"),
        "lost-key",
        FastAPIResponse(content=b'{"ok": true, "recovered": true}', status_code=200),
        payload_hash=idem_module.payload_hash(b""),
        principal_role="Registrar",
    )
    replay = client2.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "lost-key"})
    assert replay.status_code == 200
    assert replay.json()["recovered"] is True
    assert counters["w2"]["calls"] == 0, "replay, not re-execution"


def test_redis_unavailable_falls_back_to_in_memory(monkeypatch):
    """Redis down → per-process behavior (original PR-6 contract), no crash."""
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._client = None
    claim._available = False
    idem_module._distributed_claim = claim
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9001
    )

    try:
        counter = {"calls": 0}
        app = _make_app(counter)
        client = TestClient(app, raise_server_exceptions=False)

        h1 = auth_headers("1")
        r1 = client.post("/echo", headers={**h1, "Idempotency-Key": "mem-key"})
        assert r1.status_code == 200
        r2 = client.post("/echo", headers={**h1, "Idempotency-Key": "mem-key"})
        assert r2.status_code == 200
        assert counter["calls"] == 1, "in-memory dedup still works in fallback"
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve


def test_store_response_snapshot_round_trip(fake_redis):
    """Snapshot is JSON+base64 and replays status/headers/body faithfully."""
    claim = _make_claim(fake_redis)
    from starlette.responses import Response

    original = Response(
        content=b'{"invoice_id": 42}',
        status_code=200,
        headers={"X-Custom": "abc"},
        media_type="application/json",
    )
    claim.store_response(7, "k", original, payload_hash="deadbeef", principal_role="Registrar")
    replayed, stored_hash, stored_role = claim.load_response(7, "k")
    assert replayed is not None
    assert replayed.status_code == 200
    assert replayed.body == b'{"invoice_id": 42}'
    assert replayed.headers.get("x-custom") == "abc"
    assert stored_hash == "deadbeef"
    assert stored_role == "Registrar"


# =====================================================================
# Codex R2 #3092
# =====================================================================


def test_changed_payload_with_reused_key_gets_409_not_original_success(two_workers):
    """Codex R2 #3092 (P1): cart committed, response lost, registrar changed a
    doctor/price and retried with the SAME key → 409 Conflict, never the
    original success replayed over different data. Same-payload retry still
    replays."""
    client1, client2, counters, _ = two_workers
    key = "codex-r2-payload-binding"
    h1 = auth_headers("1")

    first = client1.post("/echo", json={"doctor": 1}, headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # Registrar changed the cart before retrying — same key, different body
    changed = client2.post("/echo", json={"doctor": 2}, headers={**h1, "Idempotency-Key": key})
    assert changed.status_code == 409
    assert "different request payload" in changed.text
    # The changed retry must NOT execute the handler either
    assert counters["w2"]["calls"] == 0

    # Unchanged retry (lost-response replay scenario) still replays the
    # original 200 with the original body.
    same = client2.post("/echo", json={"doctor": 1}, headers={**h1, "Idempotency-Key": key})
    assert same.status_code == 200
    assert same.json()["ok"] is True
    assert counters["w2"]["calls"] == 0


def test_changed_payload_local_cache_mismatch_returns_409(two_workers):
    """Local (same-worker) path: cached response + different body → 409."""
    client1, client2, counters, _ = two_workers
    key = "codex-r2-local-mismatch"
    h1 = auth_headers("1")

    first = client1.post("/echo", json={"v": 1}, headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    second = client1.post("/echo", json={"v": 999}, headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 409
    assert counters["w1"]["calls"] == 1, "changed payload must not execute the handler"


def test_in_flight_lease_is_short_not_24h(fake_redis):
    """Codex R2 #3092 (P2): the claim lives lease_seconds (90s), not the
    response TTL — a dead worker 409-locks its key for seconds, not a day."""
    claim = _make_claim(fake_redis)
    token = claim.acquire(1, "lease-key")
    assert token, "acquire returns the ownership token (Codex R3)"
    claim_ttl = fake_redis.ttls["idem:1:lease-key:claim"]
    assert claim_ttl == claim.lease_seconds
    assert claim_ttl < 24 * 60 * 60
    assert claim_ttl == 90


def test_lease_renewal_extends_only_existing_claim(fake_redis):
    """renew() extends a live claim (owner-token CAS) and never resurrects
    a lapsed one."""
    claim = _make_claim(fake_redis)
    token = claim.acquire(1, "renew-key")
    assert token
    assert fake_redis.store["idem:1:renew-key:claim"] == token
    assert claim.renew(1, "renew-key", token) is True
    assert fake_redis.ttls["idem:1:renew-key:claim"] == 90

    # Lapsed claim (worker died, TTL elapsed) — renewal must NOT resurrect it
    fake_redis.store.pop("idem:1:renew-key:claim")
    assert claim.renew(1, "renew-key", token) is False
    assert "idem:1:renew-key:claim" not in fake_redis.store


def test_transient_redis_failure_recovers(monkeypatch, fake_redis):
    """Codex R2 #3092 (P1): a Redis timeout/restart degrades the layer, then
    coordination RESUMES after the cooldown — the worker is not permanently
    disabled until restart."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    claim = _make_claim(fake_redis)

    # Simulate a transient failure: the next op raises
    fake_redis.fail_next_ops = 1
    assert claim.acquire(1, "recover-key") is None  # op failed → refuse execution
    assert claim.available is False

    # Cooldown elapsed (0s): the next acquire re-probes and succeeds
    token = claim.acquire(1, "recover-key")
    assert token, "recovered acquire returns a fresh owner token"
    assert claim.available is True
    assert fake_redis.store["idem:1:recover-key:claim"] == token


def test_redis_url_redacted_in_logs(monkeypatch, caplog):
    """Codex R2 #3092 (P1): credentials in the Redis URI never reach logs."""
    import logging as _logging

    class _PingingFake:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr(
        idem_module.redis_lib.Redis,
        "from_url",
        classmethod(lambda cls, url, **kwargs: _PingingFake()),
    )

    import app.middleware.idempotency_middleware as m

    with caplog.at_level(_logging.INFO, logger=m.logger.name):
        DistributedIdempotencyClaim("redis://:S3cretPassword@redis-host:6379/0")

    assert "S3cretPassword" not in caplog.text
    assert "redis-host:6379" in caplog.text

    # The pure helper behaves identically on URL-like strings
    redacted = idem_module.redact_redis_url("redis://user:pw@host:6380/2")
    assert "pw" not in redacted and "user" not in redacted
    assert redacted.startswith("redis://host:6380/2")


# =====================================================================
# Codex R3 #3092
# =====================================================================


def test_stale_owner_cannot_renew_or_release_replacement_claim(fake_redis):
    """Codex R3 #3092 (P1): a worker whose lease lapsed cannot renew or delete
    the claim re-acquired by another owner. renew = compare-and-expire,
    release = compare-and-delete over the ownership token. Previously SET XX
    only checked existence, so the stale worker overwrote the replacement and
    its unconditional release deleted a live claim — a third request could
    then execute and duplicate visits/invoices/queue positions."""
    claim = _make_claim(fake_redis)

    stale_token = claim.acquire(1, "owner-key")
    assert stale_token

    # Lease lapsed (Redis outage / long pause); another worker acquired the key
    fake_redis.store.pop("idem:1:owner-key:claim")
    fresh_token = claim.acquire(1, "owner-key")
    assert fresh_token and fresh_token != stale_token

    # Stale owner's renewal must NOT overwrite the replacement claim
    assert claim.renew(1, "owner-key", stale_token) is False
    assert fake_redis.store["idem:1:owner-key:claim"] == fresh_token

    # Stale owner's release must NOT delete the live claim
    claim.release(1, "owner-key", stale_token)
    assert fake_redis.store["idem:1:owner-key:claim"] == fresh_token

    # The CURRENT owner can still renew and release
    assert claim.renew(1, "owner-key", fresh_token) is True
    claim.release(1, "owner-key", fresh_token)
    assert "idem:1:owner-key:claim" not in fake_redis.store


def test_unverified_principal_bypasses_idempotency_entirely(two_workers):
    """Codex R3 #3092 (P1): no/garbage bearer token → the middleware must not
    store or replay anything (the shared user-0 namespace is gone). Both
    requests execute; nothing lands in Redis under that key."""
    client1, client2, counters, fake_redis = two_workers

    r1 = client1.post("/echo", headers={"Idempotency-Key": "anon-key"})
    assert r1.status_code == 200
    r2 = client2.post("/echo", headers={"Idempotency-Key": "anon-key"})
    assert r2.status_code == 200
    assert counters["w1"]["calls"] == 1
    assert counters["w2"]["calls"] == 1, (
        "unauthenticated requests bypass idempotency — no cross-user replay"
    )
    assert not any("anon-key" in k for k in fake_redis.store), (
        "nothing may be stored without a verified principal"
    )

    # A garbage token is equally untrusted
    bad = client2.post(
        "/echo",
        headers={"Authorization": "Bearer not-a-jwt", "Idempotency-Key": "anon-key"},
    )
    assert bad.status_code == 200
    assert counters["w2"]["calls"] == 2


def test_verified_principal_replays_across_workers(two_workers):
    """Codex R3 #3092 (P1): with a verified principal the R1 cross-worker
    replay guarantee still holds — the namespace is derived from the token."""
    client1, client2, counters, _ = two_workers
    key = "verified-replay"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 0, "same verified principal → replay, not re-execution"


def test_cross_principal_replay_is_blocked(two_workers):
    """Codex R3 #3092 (P1): two verified principals sharing one key + body
    never see each other's cached response — the namespaces differ because
    they are derived from each verified sub claim."""
    client1, client2, counters, _ = two_workers
    key = "shared-key"
    h1 = auth_headers("1")
    h2 = auth_headers("2")

    first = client1.post("/echo", json={"v": 1}, headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    second = client2.post("/echo", json={"v": 1}, headers={**h2, "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 1, (
        "principal 2 must execute its own handler, never replay principal 1's response"
    )


def test_replay_refused_when_principal_no_longer_authorized(two_workers, monkeypatch):
    """Codex R3 #3092 (P1): replay happens only AFTER authorization. A cached
    2xx must not be served to a principal that no longer passes the DB check.

    Codex R8 #3092 (P1): the refusal is now NON-EXECUTING — the guarded write
    must not run for a refused principal (the endpoint does NOT re-verify
    is_active, so the old fall-through executed the command and duplicated
    committed state on retry). 403 + no execution + snapshot kept."""
    client1, client2, counters, _ = two_workers
    key = "revoked-key"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # The DB authorization check now fails for this principal
    original_check = idem_module._check_principal_authorized_sync
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (False, None, False)
    )
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 403  # non-executing refusal (Codex R8)
    assert counters["w2"]["calls"] == 0, (
        "unauthorized principal must not receive the cached response NOR re-execute the write"
    )

    # After the principal is authorized again, the SAME key replays the
    # stored snapshot (it was kept, not evicted).
    monkeypatch.setattr(idem_module, "_check_principal_authorized_sync", original_check)
    third = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert third.status_code == 200
    assert counters["w2"]["calls"] == 0, "snapshot survives the refusal"


def test_principal_authorization_check_fails_closed(fake_redis, monkeypatch):
    """The DB-backed check must fail CLOSED: a broken DB session refuses
    authorization instead of allowing a replay. The check runs against the
    SAME session source the endpoint uses (get_db, or its dependency
    override in the test world)."""
    from types import SimpleNamespace

    from app.api.deps import get_db
    from app.middleware.idempotency_middleware import _check_principal_authorized_sync

    class BrokenSession:
        def execute(self, *a, **k):
            raise RuntimeError("simulated DB outage")

    def broken_override():
        yield BrokenSession()

    request = SimpleNamespace(
        app=SimpleNamespace(dependency_overrides={get_db: broken_override})
    )
    assert _check_principal_authorized_sync(request, 1, None, None)[0] is False
    assert _check_principal_authorized_sync(request, None, None, None)[0] is False


def test_authorization_resolves_through_dependency_override():
    """The check must query the SAME DB the endpoint authenticates against:
    when the app overrides get_db (test world), the middleware follows the
    override instead of opening a second connection to another database."""
    from types import SimpleNamespace

    from app.api.deps import get_db
    from app.middleware.idempotency_middleware import _check_principal_authorized_sync

    class SessionSpy:
        def __init__(self) -> None:
            self.used = False

        def execute(self, stmt):
            self.used = True
            # user found, active, not blacklisted, role Registrar, not superuser
            return SimpleNamespace(first=lambda: (7, True, "Registrar", False, False, False))

    class Override:
        def __init__(self) -> None:
            self.session = SessionSpy()

        def __call__(self):
            yield self.session

    override = Override()
    request = SimpleNamespace(app=SimpleNamespace(dependency_overrides={get_db: override}))
    authorized, role, is_superuser = _check_principal_authorized_sync(request, 7, None, None)
    assert authorized is True
    assert role == "Registrar"
    assert is_superuser is False
    assert override.session.used, "the override session (endpoint's DB) must be queried"


def test_namespace_is_stable_per_canonical_user_and_hashed():
    """The namespace is a deterministic hash of the CANONICAL user id —
    no raw usernames/ids in cache keys, no collisions between principals
    (Codex R11 #3092: derived from the DB-resolved id, not the raw sub)."""
    from hashlib import sha256

    ns1 = IdempotencyMiddleware._namespace(1)
    ns1_again = IdempotencyMiddleware._namespace(1)
    ns2 = IdempotencyMiddleware._namespace(2)
    assert ns1 == ns1_again
    assert ns1 != ns2
    assert ns1 == sha256(b"user:1").hexdigest()[:32]


def test_login_and_refresh_token_shapes_share_one_namespace(two_workers, monkeypatch):
    """Codex R11 #3092 (P1): a mobile login token carries sub=username,
    /mobile/auth/refresh re-issues sub=user.id (+username claim) — the SAME
    key sent before and after the refresh must land in ONE namespace: the
    retry after the refresh REPLAYS the stored outcome instead of
    re-executing the write (duplicate appointment)."""
    client1, client2, counters, fake_redis = two_workers
    key = "refresh-storm-key"

    # Attempt 1: login-shape token (sub=username, no username claim)
    from datetime import UTC, datetime, timedelta

    import jwt as pyjwt

    from app.core.config import settings

    login_payload = {
        "sub": "alice.smith",  # username shape — the harness stub must map it
        "exp": datetime.now(UTC) + timedelta(minutes=5),
    }
    login_token = pyjwt.encode(login_payload, settings.SECRET_KEY, algorithm="HS256")

    # The canonical resolution maps the username to user id 1 (stub seam)
    monkeypatch.setattr(
        idem_module,
        "_resolve_principal_id_sync",
        lambda request, user_id, username: 1 if username == "alice.smith" else user_id,
    )

    first = client1.post("/echo", headers={**{"Authorization": f"Bearer {login_token}"}, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # Attempt 2 (retry after refresh): refresh-shape token — sub="1",
    # username claim present. SAME key, same (empty) payload.
    second = client2.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 0, (
        "the post-refresh retry must REPLAY the stored outcome (one namespace), not re-execute"
    )


def test_unresolvable_principal_is_refused_non_executing(two_workers, monkeypatch):
    """Codex R11 #3092 (P1): a principal that does NOT resolve to a DB row
    (deleted user / broken resolution) has NO namespace — fail CLOSED with
    the non-executing 403 (Codex R8 contract): the endpoint never runs
    (nothing commits), nothing is stored or replayed under any namespace."""
    client1, client2, counters, fake_redis = two_workers
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    monkeypatch.setattr(idem_module, "_patient_replay_policy_sync", lambda request, canonical_id: ("", False, True))
    monkeypatch.setattr(idem_module, "_resolve_principal_id_sync", lambda *a, **k: None)

    response = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "ghost-key"})
    assert response.status_code == 403
    assert counters["w1"]["calls"] == 0, "non-executing refusal"

    # Nothing was stored under ANY namespace: after the resolution recovers,
    # the same key executes fresh (no stale replay surface exists).
    monkeypatch.setattr(idem_module, "_patient_replay_policy_sync", saved_patient_policy)
    monkeypatch.setattr(idem_module, "_resolve_principal_id_sync", saved_resolve)
    response2 = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "ghost-key"})
    assert response2.status_code == 200
    assert counters["w1"]["calls"] == 1


# =====================================================================
# Codex R4 → R6 #3092: role binding at replay
# =====================================================================


def test_post_inflight_replay_is_authorized_too(two_workers, monkeypatch):
    """Codex R4 #3092 (P1): the post-in-flight re-check branch must run the
    same authorization as the earlier replay branches — a revoked principal
    must not receive the cached response that landed between its failed
    acquire and the second lookup."""
    client1, client2, counters, fake_redis = two_workers
    key = "post-inflight-auth"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # A stale claim is present, so worker 2's acquire fails; the re-check
    # then finds the snapshot — and must authorize BEFORE replaying.
    fake_redis.store[nkey("1", key, "claim")] = uuid.uuid4().hex
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (False, None, False)
    )
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    # Codex R8 #3092 (P1): non-executing refusal instead of fall-through.
    assert second.status_code == 403
    assert counters["w2"]["calls"] == 0, (
        "post-inflight replay must not bypass authorization NOR re-execute the write"
    )


def test_execute_path_refused_principal_does_not_execute(two_workers, monkeypatch):
    """Codex R8 #3092 (P1): the execute path must not run the guarded write
    for a principal the DB authorization refuses (deactivated user with a
    still-valid token — get_current_user/require_roles never check
    is_active). The refusal is a non-executing 403: no handler call, no
    stored outcome, claim released — after reactivation the same key
    executes fresh."""
    client1, client2, counters, fake_redis = two_workers
    key = "deactivated-registrar"
    h1 = auth_headers("1")

    original_check = idem_module._check_principal_authorized_sync
    # The user was deactivated AFTER login: canonical auth would let the
    # request through, but the DB authorization check refuses it.
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (False, None, False)
    )
    refused = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert refused.status_code == 403
    assert counters["w2"]["calls"] == 0, (
        "a refused principal must never reach the handler (no duplicate commits)"
    )
    assert not any("deactivated-registrar" in k for k in fake_redis.store), (
        "no outcome is stored for a refused principal"
    )

    # Reactivation: the same key now executes normally (nothing was stored).
    monkeypatch.setattr(idem_module, "_check_principal_authorized_sync", original_check)
    retry = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert retry.status_code == 200
    assert counters["w2"]["calls"] == 1


def test_require_roles_publishes_policy_for_introspection():
    """Codex R6 #3092 (P1): the SSOT require_roles factory publishes the
    normalized roles on its dependency callable — the idempotency middleware
    reads this attribute to evaluate the endpoint policy at replay time.
    No policy duplication, no drift."""
    from app.core.security import require_roles

    dep = require_roles("Admin", "Registrar")
    assert getattr(dep, "required_roles", None) == ("Admin", "Registrar")


def test_role_change_between_authorized_roles_replays_snapshot(two_workers, monkeypatch):
    """Codex R6 #3092 (P1): /registrar/cart accepts BOTH Admin and Registrar.
    A role change between two roles the endpoint still authorizes must
    REPLAY the committed snapshot — the R4 label-comparison evicted it and
    the authorized retry re-executed the write (duplicate visits, invoices
    and queue entries after a lost response)."""
    client1, client2, counters, _ = two_workers
    key = "role-policy-replay"
    h1 = auth_headers("1")

    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Admin", False)
    )
    first = client1.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # The same principal is now a Registrar — still authorized by the policy.
    # Cross-worker retry: the distributed snapshot must be replayed.
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Registrar", False)
    )
    second = client2.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 0, (
        "role change between two allowed roles → replay the committed outcome, not re-execution"
    )

    # Same-worker retry (w1 holds the local cache entry from the first
    # request) exercises the LOCAL cache branch with the same policy
    third = client1.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert third.status_code == 200
    assert counters["w1"]["calls"] == 1


def test_role_change_to_unauthorized_role_refuses_but_keeps_snapshot(two_workers, monkeypatch):
    """Codex R6 #3092 (P1): when the endpoint policy refuses the new role the
    replay falls through (require_roles 403s + audits exactly as for a fresh
    request), but the committed snapshot is KEPT — when the principal regains
    an allowed role, the same-key retry replays again instead of re-executing
    the write."""
    client1, client2, counters, _ = two_workers
    key = "role-policy-refuse"
    h1 = auth_headers("1")

    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Admin", False)
    )
    first = client1.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # Demoted to a role the endpoint does not accept → no replay.
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Doctor", False)
    )
    second = client2.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200  # fell through (the endpoint 403s in production)
    assert counters["w2"]["calls"] == 1, "policy-refused role must not receive the cached response"

    # Re-promoted → the SAME snapshot replays (retention, not eviction).
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Admin", False)
    )
    third = client2.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert third.status_code == 200
    assert counters["w2"]["calls"] == 1, "re-promoted principal replays the retained snapshot"


def test_superuser_replays_across_role_change(two_workers, monkeypatch):
    """Codex R6 #3092 (P1): require_roles lets superusers through regardless
    of the role label — the replay policy must honor the same bypass, so a
    superuser whose role label changed still replays the committed snapshot."""
    client1, client2, counters, _ = two_workers
    key = "superuser-replay"
    h1 = auth_headers("1")

    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Admin", False)
    )
    first = client1.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Doctor", True)
    )
    second = client2.post("/cart-like", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 0, "superuser bypass → replay, not re-execution"


def test_role_permitted_treats_empty_policy_as_unknown():
    """Codex R12 #3092 (P1): a matched route WITHOUT a require_roles
    dependency resolves to an EMPTY allowed set — that is INSUFFICIENT
    POLICY INFORMATION, not unrestricted access. The middleware cannot
    statically evaluate handler-level (inline) authorization, so the
    replay decision must fall back to the conservative R4 comparison
    (same role → replay, changed role → refuse/re-execute) instead of
    unconditionally replaying."""
    from types import SimpleNamespace

    middleware = IdempotencyMiddleware(app=None)
    request = SimpleNamespace(scope={})
    # Instance-level shadow of the resolver (no class-attribute mutation —
    # _endpoint_allowed_roles is a staticmethod and must stay untouched for
    # the resolver test below).
    middleware._endpoint_allowed_roles = lambda req: frozenset()
    assert middleware._role_permitted_for_replay(request, "Registrar", "Cashier", False) is None
    # Same-role replay keeps working through the R4 fallback (handled by
    # the caller: None + unchanged role label → replay).
    assert middleware._role_permitted_for_replay(request, "Registrar", "Registrar", False) is None


def test_role_change_does_not_bypass_inline_authorization(two_workers, monkeypatch):
    """Codex R12 #3092 (P1): re-run inline authorization before replay.

    An endpoint that enforces authorization INSIDE the handler (no
    require_roles — mirror of queue.py:533-606: get_current_user +
    can_read_queue + doctor-ownership) must not have its cached response
    replayed after a role change: the empty allowed set does not authorize
    the new role. The retry must fall through so the INLINE authorization
    re-runs and 403s the now-unauthorized role instead of exposing the
    cached patient_name."""
    client1, client2, counters, _ = two_workers
    key = "inline-authz-role-change"
    h1 = auth_headers("1")

    # Registrar passes the inline check; the response (with patient_name)
    # is committed and stored under the Registrar role.
    first = client1.post("/inline-auth", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["inline"]["calls"] == 1

    # Same-role replay still works (R4 fallback: unchanged role label).
    same_role = client2.post("/inline-auth", headers={**h1, "Idempotency-Key": key})
    assert same_role.status_code == 200
    assert counters["w2"]["inline"]["calls"] == 0, (
        "same-role replay must not re-execute the handler"
    )

    # The principal's role changes (Registrar → Cashier); the handler's
    # INLINE authorization now refuses (can_read_queue / ownership fail).
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Cashier", False)
    )
    counters["w2"]["inline"]["allowed"] = False

    second = client2.post("/inline-auth", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 403, (
        "empty allowed set must NOT authorize a role-changed replay — "
        "the inline authorization must re-run"
    )
    assert counters["w2"]["inline"]["calls"] == 1, (
        "the handler (inline authorization) must have re-executed"
    )
    assert "patient_name" not in second.text, (
        "the cached Registrar response must not be exposed to the Cashier role"
    )


def test_role_change_with_unknown_policy_blocks_replay(two_workers, monkeypatch):
    """Codex R4 fallback preserved: when the endpoint policy CANNOT be
    determined (no app in scope / no matching route), a changed role label
    still refuses the replay and evicts the stale binding so the
    re-execution re-stores with the fresh role."""
    client1, client2, counters, _ = two_workers
    key = "unknown-policy"
    h1 = auth_headers("1")

    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Registrar", False)
    )
    monkeypatch.setattr(
        IdempotencyMiddleware, "_endpoint_allowed_roles", lambda self, request: None
    )
    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Doctor", False)
    )
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200  # re-executed under the new role
    assert counters["w2"]["calls"] == 1, (
        "unknown policy + changed role → conservative re-execution, no replay"
    )

    # Each further same-role retry replays the response stored under the
    # CURRENT role binding (no endless refusals, no duplicate executions)
    third = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert third.status_code == 200
    assert counters["w2"]["calls"] == 1


def test_endpoint_allowed_roles_resolves_matched_route():
    """Codex R6 #3092 (P1): the policy resolver walks the app router, matches
    the request scope against the routes and unions the published
    required_roles of the matched route's dependencies; an unrestricted
    route resolves to an empty frozenset (any authenticated principal)."""
    from types import SimpleNamespace

    middleware = IdempotencyMiddleware(app=None)

    class _Route:
        def __init__(self, path: str, roles) -> None:
            self.path = path
            self._roles = roles

        def matches(self, scope):
            from starlette.routing import Match

            if scope.get("path") == self.path and scope.get("method") == "POST":
                return Match.FULL, {}
            return Match.NONE, {}

        @property
        def dependant(self):
            dep = SimpleNamespace(call=_policy_dep)
            return SimpleNamespace(dependencies=[dep])

    class _App:
        def __init__(self, routes) -> None:
            self.router = SimpleNamespace(routes=routes)

    request = SimpleNamespace(scope={"path": "/cart-like", "method": "POST"})
    app = _App([
        _Route("/cart-like", _policy_dep.required_roles),
    ])
    request.scope["app"] = app
    assert middleware._endpoint_allowed_roles(request) == frozenset({"admin", "registrar"})


def test_execute_path_authorizes_once_and_retains_outcome(two_workers, monkeypatch):
    """Codex R6 #3092 (P1): the authorized role is established BEFORE
    execution (single DB query per keyed request) and the committed outcome
    is retained UNCONDITIONALLY — the old post-commit re-check lost the
    snapshot on a transient DB failure after /registrar/cart had already
    committed, and the claim expiry then duplicated the write on the
    lost-response retry."""
    calls = {"n": 0}

    def spy(*a, **k):
        calls["n"] += 1
        return (True, "Registrar", False)

    monkeypatch.setattr(idem_module, "_check_principal_authorized_sync", spy)
    client1, client2, counters, _ = two_workers
    key = "pre-exec-authz"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1
    assert calls["n"] == 1, (
        "exactly ONE DB authorization query (pre-execution); the post-commit re-check is gone"
    )

    # The committed outcome is retained: a lost-response retry on another
    # worker replays it (the replay path's own authorization query is the
    # only further DB call).
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 0, "retained snapshot must replay, not re-execute"


def test_pre_execution_authorization_failure_stores_nothing(two_workers, monkeypatch):
    """Codex R6 #3092 (P1): fail-closed — when the pre-execution authorization
    cannot establish the role, nothing is stored or bound and a retry
    re-executes from scratch (no snapshot for an unverified role).

    Codex R8 #3092 (P1): the refusal is now a NON-EXECUTING 403 — the
    guarded write must not run for a refused principal (the endpoint does
    not re-verify is_active, so the old fall-through executed the command
    and duplicated committed state on a lost-response retry)."""
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (False, None, False)
    )
    client1, client2, counters, _ = two_workers
    key = "pre-exec-fail"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 403  # non-executing refusal
    assert counters["w1"]["calls"] == 0

    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 403
    assert counters["w2"]["calls"] == 0, (
        "nothing was stored for the unauthorized principal — the retry re-executes"
    )


def test_expired_token_bypasses_replay_zero_leeway(two_workers):
    """Codex R6 #3092 (P2): the middleware decodes the bearer JWT with the
    SAME zero-leeway expiry policy as get_current_user — an already-expired
    token is not a principal, bypasses idempotency entirely and can no
    longer retrieve the PHI-bearing cached response during the old 15s
    leeway window."""
    from app.core.security import create_access_token

    client1, client2, counters, _ = two_workers
    key = "expired-token"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    expired = {"Authorization": f"Bearer {create_access_token('1', expires_minutes=-1)}"}
    second = client2.post("/echo", headers={**expired, "Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 1, (
        "expired token bypasses idempotency — the endpoint re-authenticates (401 in production)"
    )


# ===================== Codex R9 #3092 (P1): canonical subject =====================


def test_replay_authorizes_by_username_claim_like_get_current_user(two_workers, monkeypatch):
    """Canonical 2FA tokens carry BOTH numeric sub and a username claim;
    get_current_user resolves the account through _subject_from_payload,
    which PREFERS the username claim. The middleware must select the same
    subject: captured authorization args must contain the USERNAME, not the
    numeric id from sub."""
    client1, client2, counters, fake_redis = two_workers

    captured: dict[str, Any] = {}

    def _spy(request, user_id, username, jti, require_active_doctor_profile=False):
        captured["user_id"] = user_id
        captured["username"] = username
        return True, "Registrar", False

    monkeypatch.setattr(idem_module, "_check_principal_authorized_sync", _spy)

    token = create_canonical_token(sub="42", username="registrar_1")
    first = client1.post(
        "/echo", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "subj-key"}
    )
    assert first.status_code == 200
    assert captured["username"] == "registrar_1", (
        "the username claim must be the primary subject, exactly like deps.py"
    )
    assert captured["user_id"] is None


def test_replay_refused_when_username_claim_no_longer_resolves(two_workers, monkeypatch):
    """After an admin RENAMES a registrar, the old token's username no longer
    exists: the endpoint's get_current_user refuses (401), so the middleware
    must refuse the replay too — previously it resolved the numeric sub and
    replayed the cached PHI-bearing cart response under a token the endpoint
    itself would reject."""
    client1, client2, counters, fake_redis = two_workers

    from app.core.security import create_access_token as _cat  # noqa: F401

    token = create_canonical_token(sub="42", username="registrar_1")

    # First request: user 'registrar_1' exists → authorized + stored.
    idem_module._check_principal_authorized_sync = _make_username_checker(
        existing={"registrar_1"}, renamed_to="registrar_2"
    )
    first = client1.post(
        "/echo", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "rename-key"}
    )
    assert first.status_code == 200

    # Admin renames the user; the SAME token now fails the endpoint's
    # username lookup (user_id=None, username='registrar_1' → not found).
    idem_module._check_principal_authorized_sync = _make_username_checker(
        existing={"registrar_2"}, renamed_to="registrar_2"
    )
    replay = client2.post(
        "/echo", headers={"Authorization": f"Bearer {token}", "Idempotency-Key": "rename-key"}
    )
    assert replay.status_code == 403, (
        "a stored response must not replay for a principal the endpoint would refuse"
    )
    assert counters["w2"]["calls"] == 0


# ── helpers for the canonical-subject tests ──


def create_canonical_token(sub: str, username: str) -> str:
    """A canonical 2FA-style token: numeric sub AND username claim."""
    from app.core.security import create_access_token

    return create_access_token({"sub": sub, "username": username})


def _make_username_checker(existing: set[str], renamed_to: str):
    """Stub of the DB authorization query with get_current_user's subject
    semantics: numeric subject → by id; text subject → by username."""

    def _checker(request, user_id, username, jti, require_active_doctor_profile=False):
        if user_id is not None:
            # Numeric subjects resolve by id in get_current_user's primary
            # lookup — but a canonical token with a username claim NEVER
            # reaches this branch (the middleware mirrors deps.py).
            return (True, "Registrar", False) if str(user_id) == "42" else (False, None, False)
        if username is None:
            return False, None, False
        if username.isdigit():
            return (True, "Registrar", False) if username == "42" else (False, None, False)
        return (True, "Registrar", False) if username in existing else (False, None, False)

    return _checker


# ===================== Codex R7 #3092 (P1×2): fail-closed coordination =====================

def _down_claim(required: bool) -> DistributedIdempotencyClaim:
    """Claim instance marked REQUIRED whose Redis is unreachable (bypasses
    from_url/ping). Cooldown is zeroed so the first try_available() probes."""
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._prefix = "idem"
    claim._lease_seconds = 90
    claim._required = required
    claim._client = FakeRedis()  # ping() raises -> unavailable
    claim._client.fail_next_ops = 10_000
    claim._available = False
    claim._failed_at = 0.0
    return claim


def test_acquire_fails_closed_no_synthetic_local_token(monkeypatch):
    """Codex R7 #3092 (P1): with Redis unavailable acquire() returns None —
    the caller REFUSES (409/503 upstream) instead of receiving the old
    synthetic "local-*" token that let two staging workers execute the same
    keyed write concurrently during an outage."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    claim = _down_claim(required=False)
    token = claim.acquire("u1", "outage-key")
    assert token is None, (
        "degraded acquire must NOT fabricate a local execution token"
    )


def test_required_redis_down_refuses_keyed_write_then_recovers(monkeypatch):
    """Explicit IDEMPOTENCY_REDIS_URL + Redis outage → keyed write is
    refused 503 (idempotency_unavailable) WITHOUT reaching the handler;
    once Redis recovers the same key executes normally."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    claim = _down_claim(required=True)
    idem_module._distributed_claim = claim
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9002
    )
    try:
        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)
        h1 = auth_headers("1")
        r1 = client.post("/echo", headers={**h1, "Idempotency-Key": "r7-key"})
        assert r1.status_code == 503, r1.text
        assert r1.json()["code"] == "idempotency_unavailable"
        assert counter["calls"] == 0, "uncoordinated execution must not happen"

        # Redis recovers → the same key proceeds exactly once
        claim._client.fail_next_ops = 0
        r2 = client.post("/echo", headers={**h1, "Idempotency-Key": "r7-key"})
        assert r2.status_code == 200, r2.text
        assert counter["calls"] == 1
        r3 = client.post("/echo", headers={**h1, "Idempotency-Key": "r7-key"})
        assert r3.status_code == 200
        assert counter["calls"] == 1, "retry replays after recovery, no re-execution"
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve


def test_optional_redis_down_keeps_in_memory_degrade(monkeypatch):
    """ARQ-fallback (NOT required) claim + outage → original R2 contract:
    traffic degrades to the per-process cache instead of failing."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    claim = _down_claim(required=False)
    idem_module._distributed_claim = claim
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9003
    )
    try:
        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)
        h1 = auth_headers("1")
        r1 = client.post("/echo", headers={**h1, "Idempotency-Key": "opt-key"})
        assert r1.status_code == 200, r1.text
        r2 = client.post("/echo", headers={**h1, "Idempotency-Key": "opt-key"})
        assert r2.status_code == 200
        assert counter["calls"] == 1, "in-memory dedup still dedups one worker"
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve


def test_explicit_idempotency_url_marks_claim_required(monkeypatch):
    """Codex R7 #3092 (P1): explicit IDEMPOTENCY_REDIS_URL → required claim
    (fail-closed on outage); the implicit ARQ_REDIS_URL fallback stays
    optional (best-effort degrade)."""
    from app.core.config import settings

    saved = idem_module._distributed_claim
    try:
        monkeypatch.setattr(settings, "IDEMPOTENCY_REDIS_URL", "redis://127.0.0.1:1/0")
        monkeypatch.setattr(settings, "ARQ_REDIS_URL", "redis://127.0.0.1:2/0")
        idem_module._distributed_claim = None
        assert idem_module.get_distributed_claim().required is True

        monkeypatch.setattr(settings, "IDEMPOTENCY_REDIS_URL", None)
        idem_module._distributed_claim = None
        assert idem_module.get_distributed_claim().required is False
    finally:
        idem_module._distributed_claim = saved


def test_compose_files_never_evict_idempotency_state():
    """Codex R7 #3092 (P1): staging and production Redis must not run an
    evicting maxmemory policy — an evicted claim/snapshot lets a same-key
    retry on the other worker duplicate billing and queue records."""
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[3]
    for compose in ("ops/compose.staging.yml", "ops/docker-compose.yml"):
        text = (repo_root / compose).read_text(encoding="utf-8")
        effective = "\n".join(
            line for line in text.splitlines() if not line.lstrip().startswith("#")
        )
        assert "noeviction" in effective, (
            f"{compose} must use --maxmemory-policy noeviction"
        )
        assert "allkeys-lru" not in effective, (
            f"{compose} must not evict idempotency claims/snapshots"
        )


def test_required_intent_write_must_be_confirmed_before_execution(monkeypatch):
    """Codex R15 #3092 (P1): Redis падает после раннего гейта (или SET маркера
    не удался) — keyed write ОТКЛОНЯЕТСЯ 503, хендлер не запускается. Прежний
    best-effort маркер существовал только локально: второй воркер его не видел,
    потерянный ответ после истечения lease приводил к повторному исполнению."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)

    class _PingOkSetFailRedis(FakeRedis):
        def set(self, key, value, nx=False, xx=False, ex=None):
            # ломается ТОЛЬКО запись intent-маркера: claim-SET (nx=True)
            # проходит, чтобы воспроизвести именно окно "маркер не записан"
            if key.endswith(":intent"):
                raise ConnectionError("simulated intent SET failure")
            return super().set(key, value, nx=nx, xx=xx, ex=ex)

    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._prefix = "idem"
    claim._lease_seconds = 90
    claim._required = True
    claim._client = _PingOkSetFailRedis()
    claim._available = True
    claim._failed_at = 0.0
    idem_module._distributed_claim = claim
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9010
    )
    try:
        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)
        h1 = auth_headers("1")
        r1 = client.post("/echo", headers={**h1, "Idempotency-Key": "intent-key"})
        assert r1.status_code == 503, r1.text
        assert r1.json()["code"] == "idempotency_unavailable"
        assert counter["calls"] == 0, (
            "unconfirmed intent must not reach the handler"
        )
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve


def test_replay_rechecks_resource_authorization_for_same_role(monkeypatch):
    """Codex R15 #3092 (P1): replay при НЕИЗМЕННОЙ роли обязан заново
    прогнать ресурсную авторизацию принципала (активный профиль Doctor —
    зеркало inline-политики queue.py): дезактивация профиля между исполнением
    и ретраем больше не отдаёт PHI-снапшот."""
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)

    calls: list[bool] = []

    def _auth_stub(request, user_id, username, jti, require_active_doctor_profile=False):
        calls.append(bool(require_active_doctor_profile))
        if require_active_doctor_profile:
            # второй вызок — replay: профиль Doctor дезактивирован
            return False, "Doctor", False
        return True, "Doctor", False

    idem_module._distributed_claim = _make_claim(FakeRedis())
    idem_module._check_principal_authorized_sync = _auth_stub
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9011
    )
    try:
        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)
        h1 = auth_headers("1")
        r1 = client.post("/echo", headers={**h1, "Idempotency-Key": "doc-key"})
        assert r1.status_code == 200, r1.text
        r2 = client.post("/echo", headers={**h1, "Idempotency-Key": "doc-key"})
        assert r2.status_code == 403, (
            f"same-role replay with a deactivated Doctor profile must be "
            f"refused non-executing, got {r2.status_code}"
        )
        assert counter["calls"] == 1
        assert any(calls), "the replay path must run the principal authorization"
        assert calls[-1] is True, (
            "the REPLAY authorization must request the active-Doctor-profile "
            "resource check (require_active_doctor_profile=True)"
        )
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve


# ─────────────────────────────────────────────────────────────────────────────
# Codex R16 #3092 (P1): eager lease renewal + atomic ownership re-verify
# before execution. The claim used to be renewed only just before call_next,
# so the PRE-EXECUTION phase (DB authorization, intent checks, distributed
# SET) could legally outlive the 90 s lease (connection-pool wait, Redis
# latency). A lapse in that window let another worker acquire the key and
# execute the same cart while this worker proceeded on stale checks.
# ─────────────────────────────────────────────────────────────────────────────


def test_lease_renewal_starts_during_preexecution_phase(two_workers, monkeypatch):
    """Eager renewal: the loop must renew WHILE the pre-execution phase
    (DB authorization) is still running, not only around call_next.

    lease_seconds=1 → loop interval = max(1.0, 0.5) = 1.0 s. The stubbed
    authorization sleeps 1.5 s, so with the eager start the first renewal
    lands at ~1.0 s (BEFORE auth_end ≈ 1.5 s). With the old placement the
    renewal task was created only after authorization — its first renewal
    could never precede auth_end."""
    import asyncio
    import time

    from starlette.responses import Response as _UnusedResponse  # noqa: F401

    client1, _client2, counters, fake = two_workers
    claim = idem_module._distributed_claim
    claim._lease_seconds = 1

    events: list[tuple[str, float]] = []
    t0 = time.monotonic()
    orig_eval = FakeRedis.eval

    def rec_eval(self, script, numkeys, key, *args):
        if "expire" in script:
            events.append(("renew", time.monotonic() - t0))
        return orig_eval(self, script, numkeys, key, *args)

    monkeypatch.setattr(FakeRedis, "eval", rec_eval)

    orig_auth = IdempotencyMiddleware._principal_authorized

    async def slow_auth(self, request, payload, **kw):
        events.append(("auth_start", time.monotonic() - t0))
        try:
            await asyncio.sleep(1.5)
            return await orig_auth(self, request, payload, **kw)
        finally:
            events.append(("auth_end", time.monotonic() - t0))

    monkeypatch.setattr(IdempotencyMiddleware, "_principal_authorized", slow_auth)

    r = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "r16-eager"})
    assert r.status_code == 200
    assert counters["w1"]["calls"] == 1

    auth_end = max(t for name, t in events if name == "auth_end")
    renews = [t for name, t in events if name == "renew"]
    assert renews, "the renewal loop must run at least once"
    assert any(t < auth_end for t in renews), (
        "lease renewal must start during the pre-execution phase (eager after "
        f"acquisition), not only around call_next: renews={renews}, auth_end={auth_end:.2f}"
    )


def test_ownership_lost_before_execution_refuses_409_not_duplicate(two_workers, monkeypatch):
    """Lease lapsed during pre-execution and ANOTHER worker re-acquired the
    key → this worker must NOT execute: CAS re-verify fails → 409 in-flight,
    handler untouched. The old code executed anyway (duplicate cart)."""
    client1, _client2, counters, fake = two_workers
    claim = idem_module._distributed_claim
    key = "r16-stolen"

    orig_intent = claim.execution_intent_exists

    def steal(user_id, k):
        # Second worker won the expired claim: the stored token is no longer
        # ours — the CAS renew below must detect the loss.
        fake.store[nkey("1", key, "claim")] = "foreign-token"
        return orig_intent(user_id, k)

    monkeypatch.setattr(claim, "execution_intent_exists", steal)

    r = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": key})
    assert r.status_code == 409, r.text
    assert r.json()["code"] == "idempotency_in_flight"
    assert counters["w1"]["calls"] == 0, "executing without ownership duplicates the write"


def test_ownership_lost_replays_outcome_stored_by_new_owner(two_workers, monkeypatch):
    """Lease lapsed, the new owner already executed and STORED the outcome →
    this worker must replay the stored response instead of executing again."""
    import json as _json

    from starlette.responses import Response as StarletteResponse

    from app.middleware.idempotency_middleware import payload_hash

    client1, _client2, counters, fake = two_workers
    claim = idem_module._distributed_claim
    key = "r16-replay-after-lapse"

    orig_intent = claim.execution_intent_exists

    def steal_and_store(user_id, k):
        fake.store[nkey("1", key, "claim")] = "foreign-token"
        claim.store_response(
            user_id,
            k,
            StarletteResponse(content=_json.dumps({"done": True}), status_code=200, media_type="application/json"),
            payload_hash=payload_hash(b""),
            principal_role="Registrar",
        )
        return orig_intent(user_id, k)

    monkeypatch.setattr(claim, "execution_intent_exists", steal_and_store)

    r = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": key})
    assert r.status_code == 200, r.text
    assert r.json() == {"done": True}, "must replay the outcome stored by the new owner"
    assert counters["w1"]["calls"] == 0, "the handler must not run a second time"


# ─────────────────────────────────────────────────────────────────────────────
# Codex R17 #3267 (post-merge verification): two confirmed defects that persist
# on main after the #3267 squash merge (8fa5af6f4).
#
# P1 — the lease-lapse replay branch (claim.renew() False → outcome stored by
#      the new owner) bound the replay to exec_role/_exec_superuser from the
#      PRE-EXECUTION authorization, which never passes
#      require_active_doctor_profile=True. An active User with role Doctor but
#      an INACTIVE Doctor profile kept the role label "Doctor", so the stored
#      PHI-bearing body was returned while every endpoint that requires an
#      active Doctor profile (e.g. legacy queue call-patient) would now 403
#      the same principal on a fresh request.
#
# P2 — the eager lease task is created BEFORE the pre-execution authorization
#      await, but the cleanup used to start only around call_next. A request
#      cancelled while awaiting the authorization never reached the cleanup:
#      the orphaned _renew_lease_loop task kept renewing the claim FOREVER
#      (asyncio.CancelledError is a BaseException — except Exception cannot
#      intercept it), so a same-key retry saw a busy claim with no executing
#      request behind it.
# ─────────────────────────────────────────────────────────────────────────────


def _plant_lapse(claim, fake, key: str, *, stored_body: dict, stored_role: str):
    """Plant a lapse scenario: the claim token is no longer ours (another
    worker re-acquired after the lease lapsed) and the new owner already
    stored its outcome. Hooked into execution_intent_exists — the last sync
    point before the CAS re-verify (same technique as the R16 tests)."""
    import json as _json

    from starlette.responses import Response as StarletteResponse

    from app.middleware.idempotency_middleware import payload_hash

    orig_intent = claim.execution_intent_exists

    def steal_and_store(user_id, k):
        fake.store[nkey("1", key, "claim")] = "foreign-token"
        claim.store_response(
            user_id,
            k,
            StarletteResponse(
                content=_json.dumps(stored_body), status_code=200, media_type="application/json"
            ),
            payload_hash=payload_hash(b""),
            principal_role=stored_role,
        )
        return orig_intent(user_id, k)

    return steal_and_store


def test_lease_lapse_replay_refused_for_inactive_doctor_profile(two_workers, monkeypatch):
    """Codex R17 #3267 (P1): the lease-lapse replay must run the SAME fresh
    replay authorization with require_active_doctor_profile=True. Active User
    + role Doctor + INACTIVE Doctor profile → non-executing 403: no stored
    body, handler never runs, snapshot kept for re-activation recovery."""
    client1, _client2, counters, fake = two_workers
    claim = idem_module._distributed_claim
    key = "r17-lapse-inactive-doctor"

    checks: list[bool] = []

    def auth(request, user_id, username, jti, require_active_doctor_profile=False):
        checks.append(bool(require_active_doctor_profile))
        if require_active_doctor_profile:
            # Doctor.user_id + Doctor.active mirror (queue.py:69-79):
            # the profile is INACTIVE while the User account is active.
            return (False, "Doctor", False)
        return (True, "Doctor", False)

    monkeypatch.setattr(idem_module, "_check_principal_authorized_sync", auth)
    monkeypatch.setattr(
        claim,
        "execution_intent_exists",
        _plant_lapse(
            claim, fake, key,
            stored_body={"patient_name": "PHI-не-для-выдачи"},
            stored_role="Doctor",
        ),
    )

    r = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": key})

    assert r.status_code == 403, f"stored body must not be returned to an inactive Doctor: {r.status_code} {r.text}"
    assert r.json() == {"detail": "Пользователь деактивирован или сессия недействительна"}
    assert "PHI" not in r.text, "the stored snapshot body must not leak"
    assert counters["w1"]["calls"] == 0, "non-executing refusal: the handler must not run"
    assert True in checks, "the replay authorization must run with require_active_doctor_profile=True"
    # Snapshot KEPT (Codex R8 contract): re-activation restores the replay.
    assert nkey("1", key, "resp") in fake.store


def test_lease_lapse_replay_replays_for_active_doctor_profile(two_workers, monkeypatch):
    """Positive control for the R17 P1 fix: the same lapse branch with an
    ACTIVE Doctor profile still replays the stored outcome (the added
    authorization must not break the legitimate path)."""
    client1, _client2, counters, fake = two_workers
    claim = idem_module._distributed_claim
    key = "r17-lapse-active-doctor"

    checks: list[bool] = []

    def auth(request, user_id, username, jti, require_active_doctor_profile=False):
        checks.append(bool(require_active_doctor_profile))
        return (True, "Doctor", False)

    monkeypatch.setattr(idem_module, "_check_principal_authorized_sync", auth)
    monkeypatch.setattr(
        claim,
        "execution_intent_exists",
        _plant_lapse(claim, fake, key, stored_body={"done": True}, stored_role="Doctor"),
    )

    r = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": key})

    assert r.status_code == 200, r.text
    assert r.json() == {"done": True}
    assert counters["w1"]["calls"] == 0
    assert True in checks


def test_cancellation_during_preexecution_authorization_stops_lease_renewals(two_workers, monkeypatch):
    """Codex R17 #3267 (P2): cancelling the request while it awaits the
    pre-execution authorization must stop the eager lease task. The old code
    cancelled it only around call_next, so the orphaned loop renewed the
    claim forever and the claim stayed busy long after the request died.

    Methodology mirrors the independent verification: lease 2 s (real
    asyncio.sleep — the loop interval is 1 s), one renewal observed BEFORE
    the cancellation (eager start works), then the event loop runs LONGER
    than the original TTL. Assert: no renewals after the cancellation, the
    claim is released (nothing was executed), no task remains pending, the
    handler never ran."""
    import asyncio
    import contextlib

    from starlette.requests import Request as StarletteRequest
    from starlette.responses import Response as StarletteResponse

    _client1, _client2, counters, fake = two_workers
    claim = idem_module._distributed_claim
    claim._lease_seconds = 2
    key = "r17-cancelled-auth"

    renews = {"n": 0}
    orig_eval = FakeRedis.eval

    def rec_eval(self, script, numkeys, k, *args):
        if "expire" in script and k == nkey("1", key, "claim"):
            renews["n"] += 1
        return orig_eval(self, script, numkeys, k, *args)

    monkeypatch.setattr(FakeRedis, "eval", rec_eval)

    entered = asyncio.Event()
    orig_auth = IdempotencyMiddleware._principal_authorized

    async def hanging_auth(self, request, payload, **kw):
        entered.set()
        await asyncio.sleep(3600)  # blocked pre-execution authorization
        return await orig_auth(self, request, payload, **kw)  # pragma: no cover

    monkeypatch.setattr(IdempotencyMiddleware, "_principal_authorized", hanging_auth)

    app = _make_app({"calls": 0})
    middleware = IdempotencyMiddleware(app)
    claim_key = nkey("1", key, "claim")

    async def scenario():
        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "POST",
            "scheme": "http",
            "path": "/echo",
            "raw_path": b"/echo",
            "root_path": "",
            "query_string": b"",
            "headers": [
                (b"host", b"test"),
                (b"authorization", auth_headers("1")["Authorization"].encode()),
                (b"idempotency-key", key.encode()),
                (b"content-length", b"0"),
            ],
            "client": ("testclient", 50000),
            "server": ("testserver", 80),
            "app": app,
        }

        async def receive():
            return {"type": "http.request", "body": b"", "more_body": False}

        request = StarletteRequest(scope, receive)

        async def call_next(_req):
            counters["w1"]["calls"] += 1  # pragma: no cover - must never run
            return StarletteResponse(content=b"{}", status_code=200)  # pragma: no cover

        dispatch_task = asyncio.create_task(middleware.dispatch(request, call_next))

        # The request is now parked INSIDE the pre-execution authorization,
        # i.e. the lease task already exists (created right before it).
        await asyncio.wait_for(entered.wait(), timeout=5)

        # Wait for the first eager renewal (interval = lease/2 = 1 s) so the
        # test proves the loop WAS running before the cancellation.
        for _ in range(60):
            if renews["n"] >= 1:
                break
            await asyncio.sleep(0.05)
        assert renews["n"] >= 1, "eager renewal must be active before the cancellation"

        dispatch_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await dispatch_task

        renews_at_cancel = renews["n"]

        # Observe LONGER than the original 2 s lease: the orphaned loop used
        # to renew here forever (control on the old code: +2 renewals, claim
        # alive past its TTL).
        await asyncio.sleep(2.6)

        assert renews["n"] == renews_at_cancel, (
            "lease task must stop renewing after the request is cancelled: "
            f"{renews['n'] - renews_at_cancel} extra renewals observed"
        )
        assert claim_key not in fake.store, (
            "claim must be released: nothing was executed (no intent marker, "
            "handler never ran), so a same-key retry must acquire immediately"
        )
        pending = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
        assert not pending, f"no task may outlive the cancelled request: {pending}"
        assert counters["w1"]["calls"] == 0

    asyncio.run(scenario())


# ─────────────────────────────────────────────────────────────────────────────
# Махмудбек R18 #3277: два остаточных дефекта middleware, существовавшие ДО
# #3277 и сохранявшиеся в main. P1 — успешный захват claim после устаревшего
# чтения допускал повторное исполнение; P2 — отказ записи intent оставлял
# ложный локальный маркер и блокировал восстановительный повтор.


def test_post_acquire_replay_when_response_lands_between_read_and_acquire(two_workers, monkeypatch):
    """Махмудбек R18 #3277 (P1): воркер B завершает запрос строго между
    первым load_response() воркера A и его успешным acquire() — A возвращает
    сохранённый исход, суммарное число исполнений остаётся равным ОДНОМУ.

    Прежний порядок перепроверял результат только при ОТКАЗЕ acquire
    (ветка post-inflight); при УСПЕШНОМ захвате код шёл к исполнению, не
    проверяя, что другой воркер уже сохранил ответ, освободил claim и
    очистил intent: наш SET NX брал освобождённый ключ, intent-проверка
    не находила ничего, CAS-продление подтверждало владение НОВЫМ claim —
    и хендлер исполнял запись второй раз (дубликаты визитов/счетов)."""
    client1, client2, counters, fake_redis = two_workers
    claim = idem_module._distributed_claim
    ns = idem_module.IdempotencyMiddleware._namespace(1, "POST:/echo")
    key = "r18-postacquire-replay"

    # Хук на уровне Redis (техника _plant_lapse): ПЕРВОЕ чтение воркера A
    # возвращает None (B ещё не завершился), и в этот момент B завершается —
    # сохраняет исход и освобождает claim.
    original_load = claim.load_response
    seen = {"first": True}

    def _load_with_b_finishing(*args, **kwargs):
        result = original_load(*args, **kwargs)
        if seen["first"]:
            seen["first"] = False
            from fastapi import Response as FastAPIResponse

            claim.store_response(
                ns,
                key,
                FastAPIResponse(content=b'{"ok": true, "calls": 1}', status_code=200),
                payload_hash=idem_module.payload_hash(b""),
                principal_role="Registrar",
            )
        return result

    monkeypatch.setattr(claim, "load_response", _load_with_b_finishing)

    second = client2.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": key})
    assert second.status_code == 200, second.text
    assert second.json() == {"ok": True, "calls": 1}, (
        "the outcome stored by the finished first attempt must be replayed"
    )
    assert counters["w2"]["calls"] == 0, (
        "a SUCCESSFUL acquire must re-check the stored outcome: the operation "
        "already completed, re-executing it duplicates visits/invoices/queue"
    )
    # Claim, захваченный для этой попытки, освобождён своим токеном —
    # повтор с тем же ключом не должен ждать истечения lease.
    assert nkey("1", key, "claim") not in fake_redis.store


def test_post_acquire_payload_mismatch_returns_409_not_second_execution(two_workers, monkeypatch):
    """Махмудбек R18 #3277 (P1, вариант с другим payload): в том же окне
    между чтением и захватом чужой исход сохранён под ДРУГИМ payload —
    повтор обязан получить 409 idempotency_payload_mismatch, а не второе
    исполнение с чужим (или своим повторным) ответом."""
    client1, client2, counters, fake_redis = two_workers
    claim = idem_module._distributed_claim
    ns = idem_module.IdempotencyMiddleware._namespace(1, "POST:/echo")
    key = "r18-postacquire-mismatch"

    original_load = claim.load_response
    seen = {"first": True}

    def _load_with_foreign_payload(*args, **kwargs):
        result = original_load(*args, **kwargs)
        if seen["first"]:
            seen["first"] = False
            from fastapi import Response as FastAPIResponse

            claim.store_response(
                ns,
                key,
                FastAPIResponse(content=b'{"ok": true, "other": "payload"}', status_code=200),
                payload_hash="0" * 64,  # не совпадает с payload_hash(b"")
                principal_role="Registrar",
            )
        return result

    monkeypatch.setattr(claim, "load_response", _load_with_foreign_payload)

    second = client2.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": key})
    assert second.status_code == 409, second.text
    assert second.json()["code"] == "idempotency_payload_mismatch"
    assert counters["w2"]["calls"] == 0, (
        "changed data under a reused key must be neither executed nor replayed"
    )
    assert nkey("1", key, "claim") not in fake_redis.store


def test_failed_intent_write_recovery_does_not_block_same_key_retry(monkeypatch):
    """Махмудбек R18 #3277 (P2): неуспешная запись intent (503, хендлер не
    запускался) не должна оставлять ложный «неизвестный исход». Локальный
    mirror, безусловно записанный mark_execution_intent, переживал отказ:
    после восстановления Redis и истечения lease повтор с тем же ключом
    получал 409 idempotency_uncertain_outcome для операции, которая
    заведомо НЕ дошла до исполнения — recovery-тупик. Теперь попытка
    убирает собственные маркеры (распределённый — по токену владельца),
    и повтор исполняется ровно один раз."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    idem_module._local_execution_intents.clear()

    class _IntentSetFailsUntilRecovery(FakeRedis):
        """Ломается ТОЛЬКО запись intent-маркера (claim-SET проходит) —
        до флага восстановления, моделирующего возврат Redis."""

        def __init__(self) -> None:
            super().__init__()
            self.fail_intent_sets = True

        def set(self, key, value, nx=False, xx=False, ex=None):
            if self.fail_intent_sets and key.endswith(":intent") and not nx:
                raise ConnectionError("simulated intent SET failure")
            return super().set(key, value, nx=nx, xx=xx, ex=ex)

    fake = _IntentSetFailsUntilRecovery()
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._prefix = "idem"
    claim._lease_seconds = 90
    claim._required = True
    claim._client = fake
    claim._available = True
    claim._failed_at = 0.0
    idem_module._distributed_claim = claim
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9012
    )
    try:
        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)
        h1 = auth_headers("1")
        key = "r18-intent-recovery"

        # Попытка 1: SET intent падает → 503, хендлер не запускается,
        # распределённого маркера нет (запись не дошла).
        r1 = client.post("/echo", headers={**h1, "Idempotency-Key": key})
        assert r1.status_code == 503, r1.text
        assert r1.json()["code"] == "idempotency_unavailable"
        assert counter["calls"] == 0
        assert nkey("1", key, "intent") not in fake.store, (
            "the failed SET must not leave a distributed intent marker"
        )
        assert nkey("1", key, "claim") not in fake.store, (
            "the refused attempt must release its claim"
        )

        # Инфраструктура восстановилась (Redis вернулся, lease истёк):
        # повтор с тем же ключом обязан исполниться один раз, а не
        # получить ложный uncertain-outcome от собственного локального
        # mirror отклонённой попытки.
        fake.fail_intent_sets = False
        r2 = client.post("/echo", headers={**h1, "Idempotency-Key": key})
        assert r2.status_code == 200, (
            f"recovery retry must execute once, not receive a false 409 "
            f"idempotency_uncertain_outcome: {r2.status_code} {r2.text}"
        )
        assert counter["calls"] == 1
        # Известный исход: intent больше не нужен.
        assert nkey("1", key, "intent") not in fake.store
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._local_execution_intents.clear()


# R19 / review #3283 (5701514498): the final lease check and the intent
# write cannot be separate operations. These assertions fail on the old SET.
@pytest.mark.parametrize("required", [False, True])
def test_r19_stale_intent_writer_never_executes(two_workers, monkeypatch, required):
    client, retry_client, counters, fake = two_workers
    claim = idem_module._distributed_claim
    claim._required = required
    key = "r19-stale-" + uuid.uuid4().hex
    original = claim.mark_execution_intent

    def paused_writer(user_id, k, owner_token=None, tokenless_marker=None):
        # A resumes after B acquired the expired lease and left an unknown
        # outcome. This boundary is AFTER dispatch's previous renew check.
        fake.store[nkey("1", key, "claim")] = "attempt-B"
        fake.store[nkey("1", key, "intent")] = "attempt-B"
        return original(user_id, k, owner_token=owner_token)

    monkeypatch.setattr(claim, "mark_execution_intent", paused_writer)
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    response = client.post("/echo", headers=headers)
    assert response.status_code == 409, response.text
    assert counters["w1"]["calls"] == 0
    assert fake.store[nkey("1", key, "intent")] == "attempt-B"
    assert fake.store[nkey("1", key, "claim")] == "attempt-B"

    # B's lease ends without a saved response. C must reconcile, never
    # execute over B's unknown commit; restore the real marking method.
    monkeypatch.setattr(claim, "mark_execution_intent", original)
    fake.delete(nkey("1", key, "claim"))
    retry = retry_client.post("/echo", headers=headers)
    assert retry.status_code == 409, retry.text
    assert retry.json()["code"] == "idempotency_uncertain_outcome"
    assert counters["w2"]["calls"] == 0


@pytest.fixture
def r19_real_claim():
    """Dedicated test-only Redis, unique namespace; never FLUSHDB."""
    import os
    from urllib.parse import urlsplit

    import redis

    url = os.getenv("TEST_IDEMPOTENCY_REDIS_URL")
    if not url:
        pytest.skip("TEST_IDEMPOTENCY_REDIS_URL not configured")
    assert urlsplit(url).hostname in {"localhost", "127.0.0.1", "::1"}
    client = redis.Redis.from_url(url, decode_responses=True)
    client.ping()  # An explicitly configured but unavailable service FAILS.
    claim = _make_claim(client)
    namespace = "review-r19-" + uuid.uuid4().hex
    key = "synthetic-operation"
    yield claim, client, namespace, key
    client.delete(
        claim._claim_key(namespace, key),
        claim._intent_key(namespace, key),
        claim._resp_key(namespace, key),
    )
    idem_module._clear_local_execution_intent(namespace, key)
    client.close()


def _r19_try_mark(claim, namespace, key, token):
    try:
        return claim.mark_execution_intent(namespace, key, owner_token=token)
    except RuntimeError:
        return False


@pytest.mark.redis
def test_r19_real_redis_stale_owner_preserves_unknown_outcome(r19_real_claim):
    claim, client, ns, key = r19_real_claim
    token_a = claim.acquire(ns, key)
    assert token_a
    assert claim.renew(ns, key, token_a)
    # Simulate expiration after that successful CAS, without a 90s sleep.
    client.pexpire(claim._claim_key(ns, key), 0)
    token_b = claim.acquire(ns, key)
    assert token_b and token_b != token_a
    assert claim.mark_execution_intent(ns, key, owner_token=token_b)

    assert _r19_try_mark(claim, ns, key, token_a) is False
    assert client.get(claim._intent_key(ns, key)) == token_b
    assert claim.clear_execution_intent_if_owner(ns, key, token_a) is False
    assert client.get(claim._intent_key(ns, key)) == token_b


@pytest.mark.redis
def test_r19_real_redis_current_claim_cannot_replace_foreign_intent(r19_real_claim):
    claim, client, ns, key = r19_real_claim
    token = claim.acquire(ns, key)
    client.set(claim._intent_key(ns, key), "previous-unknown-attempt", ex=60)
    assert _r19_try_mark(claim, ns, key, token) is False
    assert client.get(claim._intent_key(ns, key)) == "previous-unknown-attempt"


@pytest.mark.redis
def test_r19_real_redis_tokenless_call_does_not_overwrite(r19_real_claim):
    claim, client, ns, key = r19_real_claim
    client.set(claim._intent_key(ns, key), "previous-unknown-attempt", ex=60)
    assert claim.mark_execution_intent(ns, key) is False
    assert client.get(claim._intent_key(ns, key)) == "previous-unknown-attempt"


@pytest.mark.redis
def test_r19_real_redis_lost_reply_cleans_only_own_landed_intent(r19_real_claim, monkeypatch):
    claim, client, ns, key = r19_real_claim
    token = claim.acquire(ns, key)
    original_eval = client.eval

    def landed_then_timeout(script, *args):
        result = original_eval(script, *args)
        if args[0] == 2:
            assert result == 1
            raise ConnectionError("synthetic lost intent reply")
        return result

    monkeypatch.setattr(client, "eval", landed_then_timeout)
    assert claim.mark_execution_intent(ns, key, owner_token=token) is False
    assert client.get(claim._intent_key(ns, key)) == token
    assert claim.clear_execution_intent_if_owner(ns, key, token) is True
    assert client.get(claim._intent_key(ns, key)) is None


# ─────────────────────────────────────────────────────────────────────────────
# PR 3319 (owner P2, verified on main 1033c3c7b3): an OPTIONAL attempt that
# degraded to the tokenless local path (Redis down at acquire) must never use
# a tokenless marker as execution permission after Redis recovery, and its
# known-outcome cleanup must never delete a foreign attempt's intent marker.
# Window: Redis recovers BETWEEN the uncertain-outcome check (still down —
# local branch) and the intent gate (recovered — distributed SET NX). On the
# pre-fix code the degraded attempt then executed next to the foreign
# attempt and its unconditional clear_execution_intent deleted the foreign
# unknown-outcome protection (R9).


class _RecoverableOutageRedis(FakeRedis):
    """ping() raises while ``down`` — the outage window of the degrade."""

    def __init__(self) -> None:
        super().__init__()
        self.down = True

    def ping(self) -> bool:
        if self.down:
            raise ConnectionError("simulated redis outage")
        return True


def _wire_outage_claim(fake: _RecoverableOutageRedis):
    """Optional claim starting in the outage state (available=False)."""
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._prefix = "idem"
    claim._lease_seconds = 90
    claim._required = False
    claim._client = fake
    claim._available = False
    claim._failed_at = 0.0
    return claim


def test_recovered_tokenless_attempt_refuses_over_foreign_intent(monkeypatch):
    """The owner's P2 interleaving: A degrades (no claim token), B marks its
    intent, Redis recovers between A's uncertain check and A's intent gate.
    A must be refused 409 WITHOUT running the handler, and B's intent marker
    must survive (no cleanup over a foreign marker)."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    idem_module._local_execution_intents.clear()

    fake = _RecoverableOutageRedis()
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    idem_module._distributed_claim = _wire_outage_claim(fake)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9012
    )
    try:
        key = "pr3319-tokenless-over-foreign"
        intent_key = nkey("1", key, "intent")

        # Worker B already guards the key with its token-bound intent marker.
        # Invisible to A while the outage lasts (every probe fails), so A
        # degrades to the tokenless local path exactly as in the incident.
        fake.store[intent_key] = "attempt-B"

        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)

        # Recovery lands BETWEEN the uncertain-outcome check (still down —
        # takes the LOCAL branch) and the intent gate: the very next probe
        # of the degraded local uncertain check flips the outage off.
        original_local_exists = idem_module._local_execution_intent_exists

        def _recovering_local_exists(user_id, key_):
            fake.down = False
            return original_local_exists(user_id, key_)

        monkeypatch.setattr(
            idem_module, "_local_execution_intent_exists", _recovering_local_exists
        )

        response = client.post(
            "/echo", headers={**auth_headers("1"), "Idempotency-Key": key}
        )

        assert response.status_code == 409, response.text
        assert response.json()["code"] == "idempotency_in_flight"
        assert counter["calls"] == 0, (
            "a tokenless degraded attempt must never execute over a foreign intent"
        )
        assert fake.store.get(intent_key) == "attempt-B", (
            "the foreign unknown-outcome marker must survive the refusal"
        )
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._local_execution_intents.clear()
        monkeypatch.undo()


def test_recovered_tokenless_attempt_executes_once_without_foreign_intent(monkeypatch):
    """Complementary path: same degrade+recovery, but NO foreign intent —
    the tokenless SET NX wins, the handler runs exactly once, and the
    anonymous marker is cleaned by the ownership-guarded known-outcome
    cleanup (single execution preserved by the NX contract)."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    idem_module._local_execution_intents.clear()

    fake = _RecoverableOutageRedis()
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    idem_module._distributed_claim = _wire_outage_claim(fake)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9012
    )
    try:
        key = "pr3319-tokenless-clean-execution"
        intent_key = nkey("1", key, "intent")

        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)

        original_local_exists = idem_module._local_execution_intent_exists

        def _recovering_local_exists(user_id, key_):
            fake.down = False
            return original_local_exists(user_id, key_)

        monkeypatch.setattr(
            idem_module, "_local_execution_intent_exists", _recovering_local_exists
        )

        response = client.post(
            "/echo", headers={**auth_headers("1"), "Idempotency-Key": key}
        )

        assert response.status_code == 200, response.text
        assert counter["calls"] == 1
        # Known outcome: the attempt's OWN anonymous marker is gone.
        assert intent_key not in fake.store, (
            "the tokenless attempt must clean its own anonymous marker"
        )
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._local_execution_intents.clear()
        monkeypatch.undo()


def test_known_outcome_cleanup_never_deletes_foreign_marker():
    """clear_execution_intent_owned is value-bound: a tokenless cleanup
    (anonymous "1") removes only an anonymous marker; an owning cleanup
    removes only its own token-bound marker. Any foreign marker survives."""
    fake = FakeRedis()
    claim = _make_claim(fake)
    claim._lease_seconds = 90

    # Tokenless cleanup vs a foreign TOKEN-bound marker: survives.
    fake.store[claim._intent_key("1", "k1")] = "attempt-B"
    claim.clear_execution_intent_owned("1", "k1", None)
    assert fake.store[claim._intent_key("1", "k1")] == "attempt-B"

    # Tokenless cleanup vs its own anonymous marker: deleted.
    fake.store[claim._intent_key("1", "k2")] = "1"
    claim.clear_execution_intent_owned("1", "k2", None)
    assert claim._intent_key("1", "k2") not in fake.store

    # Owning cleanup vs an anonymous foreign marker: survives.
    fake.store[claim._intent_key("1", "k3")] = "1"
    claim.clear_execution_intent_owned("1", "k3", "attempt-T")
    assert fake.store[claim._intent_key("1", "k3")] == "1"

    # Owning cleanup vs its own token-bound marker: deleted.
    fake.store[claim._intent_key("1", "k4")] = "attempt-T"
    claim.clear_execution_intent_owned("1", "k4", "attempt-T")
    assert claim._intent_key("1", "k4") not in fake.store

    # codex PR 3319 P1: unique per-attempt tokenless markers. Attempt A's
    # cleanup (marker m-A) must never delete attempt B's marker (m-B), and
    # the historical shared "1" fallback must not match unique markers.
    fake.store[claim._intent_key("1", "k5")] = "marker-B"
    claim.clear_execution_intent_owned("1", "k5", "marker-A")
    assert fake.store[claim._intent_key("1", "k5")] == "marker-B"
    fake.store[claim._intent_key("1", "k6")] = "marker-A"
    claim.clear_execution_intent_owned("1", "k6", "marker-A")
    assert claim._intent_key("1", "k6") not in fake.store
    fake.store[claim._intent_key("1", "k7")] = "marker-B"
    claim.clear_execution_intent_owned("1", "k7", None)
    assert fake.store[claim._intent_key("1", "k7")] == "marker-B"


def test_tokenless_lost_set_response_cleans_own_marker(monkeypatch):
    """codex PR 3319 P2: a tokenless SET whose RESPONSE is lost (Redis
    applied the write, the attempt saw a transport error) previously left
    the anonymous marker for a full TTL with no outcome — a recovery retry
    received a false idempotency_uncertain_outcome for an operation that
    never ran. The 409 branch now cleans THIS attempt's unique marker.

    The reconnect cooldown is zeroed here ONLY so the recovery lands
    within the request window (a real 5 s cooldown keeps the intent gate
    closed for the whole request); the cooldown-bypass of the cleanup
    itself is pinned separately by
    test_owned_cleanup_bypasses_reconnect_cooldown."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    idem_module._local_execution_intents.clear()

    class _LostSetResponseRedis(_RecoverableOutageRedis):
        """The intent SET lands, then raises — the attempt sees failure."""

        def set(self, key, value, nx=False, xx=False, ex=None):
            result = super().set(key, value, nx=nx, xx=xx, ex=ex)
            if nx and key.endswith(":intent"):
                raise ConnectionError("simulated lost SET response")
            return result

    fake = _LostSetResponseRedis()
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    idem_module._distributed_claim = _wire_outage_claim(fake)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9012
    )
    try:
        key = "pr3319-lost-set-response"
        intent_key = nkey("1", key, "intent")

        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)

        original_local_exists = idem_module._local_execution_intent_exists

        def _recovering_local_exists(user_id, key_):
            fake.down = False
            return original_local_exists(user_id, key_)

        monkeypatch.setattr(
            idem_module, "_local_execution_intent_exists", _recovering_local_exists
        )

        response = client.post(
            "/echo", headers={**auth_headers("1"), "Idempotency-Key": key}
        )

        assert response.status_code == 409, response.text
        assert counter["calls"] == 0, "the handler must never run after a lost SET"
        assert intent_key not in fake.store, (
            "the landed own marker must be cleaned by the 409 branch so the "
            "recovery retry does not face a false unknown-outcome"
        )
        assert nkey("1", key, "claim") not in fake.store
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._local_execution_intents.clear()
        monkeypatch.undo()


def test_owned_cleanup_bypasses_reconnect_cooldown():
    """codex PR 3319 P2: right after a failed mark the claim is marked
    unavailable for the whole reconnect cooldown; the owned cleanup must
    still reach Redis through the direct client (best-effort, same as
    clear_execution_intent_if_owner) instead of skipping on
    _ensure_available."""
    import time as _time

    fake = FakeRedis()
    claim = _make_claim(fake)
    claim._lease_seconds = 90
    marker = "marker-abc123"
    fake.store[claim._intent_key("1", "k9")] = marker

    # Simulate the post-failed-mark state: unavailable + fresh failure time
    # (same time.time() scale as _ensure_available) under the PRODUCTION
    # cooldown — _ensure_available would refuse until the cooldown elapses.
    claim._available = False
    claim._failed_at = _time.time()
    assert claim.try_available() is False

    claim.clear_execution_intent_owned("1", "k9", marker)
    assert claim._intent_key("1", "k9") not in fake.store, (
        "the owned cleanup must bypass the reconnect cooldown (direct client)"
    )
    # codex round 3: a successful direct eval proves Redis is reachable —
    # the worker's coordination state must be restored, so the Retry-After
    # retry re-enters the distributed protocol instead of degrading to the
    # optional local path while another worker may acquire the unmarked key.
    assert claim.try_available() is True


def test_owned_cleanup_failure_keeps_local_intent_and_sets_cooldown():
    """codex #3319 post-merge P2 (comment 4039202268): when the
    compare-and-delete eval itself fails (Redis unavailable again), the
    cleanup outcome is UNVERIFIED — this attempt's marker may have landed
    despite a lost SET, or a foreign marker (R9 unknown-outcome guard) may
    own the key. The attempt must stay fail-closed: the local intent mirror
    is KEPT and the claim enters the reconnect cooldown — the failed eval
    proved nothing about Redis reachability, so the success branch's
    coordination restore must not happen either."""
    import time as _time

    class _OutageAtCleanupEval(FakeRedis):
        def eval(self, script: str, numkeys: int, key: str, *args: str) -> int:
            if "del" in script:
                raise ConnectionError("simulated redis outage at owned-cleanup eval")
            return super().eval(script, numkeys, key, *args)

    fake = _OutageAtCleanupEval()
    claim = _make_claim(fake)
    claim._lease_seconds = 90
    claim._failed_at = 0.0
    foreign = "attempt-B"
    fake.store[claim._intent_key("1", "kc1")] = foreign
    # mark_execution_intent always re-arms the local mirror before the
    # 409 branch calls the owned cleanup — model that state here.
    idem_module._mark_local_execution_intent("1", "kc1")

    claim.clear_execution_intent_owned("1", "kc1", "marker-A")

    assert fake.store[claim._intent_key("1", "kc1")] == foreign, (
        "the foreign unknown-outcome marker must survive the failed cleanup"
    )
    assert idem_module._local_execution_intent_exists("1", "kc1"), (
        "a failed compare-and-delete must keep the local intent mirror"
    )
    assert claim._available is False, (
        "a failed compare-and-delete must not leave the claim 'available'"
    )
    assert 0.0 < claim._failed_at <= _time.time(), (
        "the claim must enter the reconnect cooldown on the time.time() scale"
    )
    idem_module._local_execution_intents.clear()


def test_failed_owned_cleanup_keeps_fast_retries_fail_closed(monkeypatch):
    """codex #3319 post-merge P2, full dispatch reproduction: A degrades
    tokenless (full transport outage), Redis recovers, A's tokenless SET NX
    is rejected over a foreign intent, and Redis goes down AGAIN before the
    409-branch owned-cleanup eval. The failed cleanup previously deleted the
    local mirror and left the claim 'available', so the two fast retries the
    client sends after the 409's Retry-After behaved exactly as codex
    described: retry 1 hit the stale-'available' acquire whose transport
    failure finally marked Redis unavailable (409 in-flight), and retry 2 —
    still inside the reconnect cooldown — skipped every distributed check,
    found no mirror on the local-degrade path, and EXECUTED the handler over
    the foreign attempt's unknown outcome. The mirror must survive and the
    claim must sit in the cooldown so every retry reconciles (409 uncertain)
    instead of duplicating the write."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    idem_module._local_execution_intents.clear()

    class _FullOutageAtCleanupRedis(_RecoverableOutageRedis):
        """A REAL transport outage: while ``down`` EVERY op raises. The
        ping-only outage of the base class lets EXISTS/GET/SET through,
        which would mask the degraded local path this test pins. Arms the
        second outage when the tokenless SET NX is rejected."""

        def __init__(self) -> None:
            super().__init__()
            self.fail_cleanup_eval = False

        def _raise_if_down(self) -> None:
            if self.down:
                raise ConnectionError("simulated redis outage")

        def ping(self) -> bool:
            self._raise_if_down()
            return True

        def get(self, key):
            self._raise_if_down()
            return super().get(key)

        def set(self, key, value, nx=False, xx=False, ex=None):
            self._raise_if_down()
            result = super().set(key, value, nx=nx, xx=xx, ex=ex)
            if nx and key.endswith(":intent") and result is None:
                # SET NX rejected over the foreign intent: Redis goes down
                # again right before the 409-branch owned-cleanup eval.
                self.fail_cleanup_eval = True
            return result

        def exists(self, key):
            self._raise_if_down()
            return super().exists(key)

        def eval(self, script, numkeys, key, *args):
            if self.fail_cleanup_eval and "del" in script:
                self.fail_cleanup_eval = False
                self.down = True  # the outage persists through the retries
                raise ConnectionError("simulated redis outage at owned-cleanup eval")
            self._raise_if_down()
            return super().eval(script, numkeys, key, *args)

    fake = _FullOutageAtCleanupRedis()
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: ("", False, True)
    idem_module._distributed_claim = _wire_outage_claim(fake)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9012
    )
    try:
        key = "pr3319-cleanup-failure-fail-closed"
        intent_key = nkey("1", key, "intent")

        # Worker B guards the key with its intent marker (unknown outcome).
        fake.store[intent_key] = "attempt-B"

        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)

        # Recovery lands BETWEEN the uncertain-outcome check (still down —
        # takes the LOCAL branch) and the intent gate, exactly as in the
        # incident the sibling test pins.
        original_local_exists = idem_module._local_execution_intent_exists

        def _recovering_local_exists(user_id, key_):
            fake.down = False
            return original_local_exists(user_id, key_)

        monkeypatch.setattr(
            idem_module, "_local_execution_intent_exists", _recovering_local_exists
        )

        first = client.post(
            "/echo", headers={**auth_headers("1"), "Idempotency-Key": key}
        )
        assert first.status_code == 409, first.text
        assert first.json()["code"] == "idempotency_in_flight"
        assert counter["calls"] == 0, (
            "the tokenless attempt must never execute over a foreign intent"
        )
        assert fake.store.get(intent_key) == "attempt-B", (
            "the foreign marker must survive the refused attempt"
        )

        # The outage persists; restore the PRODUCTION cooldown so the fast
        # retries (Retry-After: 1 < 5 s) run INSIDE it and skip every
        # distributed check onto the local-degrade path.
        monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 5.0)
        monkeypatch.setattr(
            idem_module, "_local_execution_intent_exists", original_local_exists
        )

        for attempt in range(3):
            retry = client.post(
                "/echo", headers={**auth_headers("1"), "Idempotency-Key": key}
            )
            assert retry.status_code == 409, (
                f"retry {attempt + 1} inside the cooldown executed over the "
                f"foreign unknown outcome (duplicate write): {retry.text}"
            )
        assert counter["calls"] == 0, (
            "retries inside the cooldown must stay fail-closed on the KEPT "
            "local mirror instead of executing over the foreign outcome"
        )
        # Post-conditions of the FAILED owned cleanup: the local mirror is
        # kept and the claim is in the reconnect cooldown.
        assert any(k[1] == key for k in idem_module._local_execution_intents), (
            "the failed compare-and-delete must keep the local intent mirror"
        )
        assert idem_module._distributed_claim._available is False, (
            "the failed compare-and-delete must not leave the claim 'available'"
        )
        assert fake.store.get(intent_key) == "attempt-B"
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._local_execution_intents.clear()
        monkeypatch.undo()


# ── Round-4 (owner P1, PR #3340): rollout compatibility + scope binding ────


def _legacy_nkey(sub: str, key: str, kind: str, path: str = "/echo") -> str:
    """Redis key under the PRE-#3340 user-only namespace (the hash form the
    previous deployment used for claim/resp/intent markers)."""
    ns = IdempotencyMiddleware._namespace(int(sub))
    return f"idem:{ns}:{key}:{kind}"


def test_known_non_2xx_clears_pre_handler_legacy_intent(two_workers):
    """Round-7 (owner P1): the pre-handler legacy intent is written under
    the fence before execution. A RETURNED non-2xx is a KNOWN outcome
    (nothing committed) — the intent must be cleared and the fence released
    so old workers may re-run the request that provably did nothing."""
    client1, client2, counters, fake_redis = two_workers
    key = "bad-legacy-intent-1"
    legacy_ns = IdempotencyMiddleware._namespace(1)

    first = client1.post("/bad", headers={**auth_headers("1"), "Idempotency-Key": key})
    assert first.status_code == 400
    assert _legacy_nkey("1", key, "intent") not in fake_redis.store, (
        "the pre-handler legacy intent is cleared on a known non-2xx"
    )
    assert nkey("1", key, "intent", path="/bad") not in fake_redis.store
    assert f"idem:{legacy_ns}:{key}:claim" not in fake_redis.store, (
        "the fence is released on a known non-2xx"
    )


# ── Round-7 (owner review on 9bb31dc, PR #3340) ─────────────────────────


def test_redis_death_at_store_response_keeps_legacy_intent_and_fence(
    two_workers, monkeypatch
):
    """THE round-7 owner P1 scenario: the handler COMMITS, then Redis dies
    exactly on the store_response() call — both outcome snapshots (current
    AND legacy namespace) land nowhere, and the client may lose the HTTP
    response. Round-6 deleted the intent markers on this path (a degraded
    store looked identical to a confirmed one) and released the fence: once
    the fence lease lapsed, an old-version worker found an EMPTY legacy
    namespace — no response, no intent, no claim — and re-executed the
    committed write.

    Round-7: the legacy intent is written BEFORE the handler under the
    still-held fence, store_response() reports its outcome, and the
    non-durable path keeps EVERY unknown-outcome guard up."""
    client1, client2, counters, fake_redis = two_workers
    key = "post-commit-redis-death-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    legacy_ns = IdempotencyMiddleware._namespace(1)
    claim = idem_module._distributed_claim

    real_set = fake_redis.set

    def dying_set(key_, value_, **kwargs):
        if key_.endswith(":resp"):
            raise ConnectionError("simulated redis outage at store_response")
        return real_set(key_, value_, **kwargs)

    monkeypatch.setattr(fake_redis, "set", dying_set)
    try:
        first = client1.post("/echo", headers=headers)
    finally:
        monkeypatch.undo()

    # The write is COMMITTED and the response still reaches the client.
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # No snapshot landed anywhere…
    assert nkey("1", key, "resp") not in fake_redis.store
    assert _legacy_nkey("1", key, "resp") not in fake_redis.store
    # …but the PRE-HANDLER legacy intent did (Redis was alive until the
    # store), and every unknown-outcome guard stays up.
    assert _legacy_nkey("1", key, "intent") in fake_redis.store, (
        "the pre-handler legacy intent must survive the post-commit outage — "
        "old workers reconcile against it instead of an empty namespace"
    )
    assert nkey("1", key, "intent") in fake_redis.store, (
        "the new-namespace intent stays up for same-key retries"
    )
    assert f"idem:{legacy_ns}:{key}:claim" in fake_redis.store, (
        "the fence is NOT released on a non-durable outcome (lapses with its lease)"
    )

    # Redis recovers (the outage was transient). The retry emulates a COLD
    # second worker: this harness shares one process, so the shared local
    # response cache (populated before the doomed distributed store) must be
    # cleared — the client that lost the response retries from elsewhere.
    claim._available = True
    claim._failed_at = 0.0
    idem_module._idempotency_cache.clear()
    retry = client2.post("/echo", headers=headers)
    assert retry.status_code == 409
    assert retry.json()["code"] == "idempotency_in_flight"
    assert counters["w2"]["calls"] == 0

    # The leases lapse (fence + claim TTLs simulated away) — the exact
    # old-version-protocol moment: the legacy namespace holds an INTENT
    # without a response, which the old worker's own R9 contract refuses.
    del fake_redis.store[f"idem:{legacy_ns}:{key}:claim"]
    del fake_redis.store[nkey("1", key, "claim")]
    late_retry = client2.post("/echo", headers=headers)
    assert late_retry.status_code == 409
    assert late_retry.json()["code"] == "idempotency_uncertain_outcome"
    assert counters["w1"]["calls"] == 1 and counters["w2"]["calls"] == 0, (
        "one logical submit, one execution — the committed write is never re-run"
    )


def test_legacy_intent_mark_transport_failure_is_fail_closed_for_required(
    two_workers, monkeypatch
):
    """Round-7 (owner P1): REQUIRED coordination dies BETWEEN the two intent
    marks — the legacy guard could not be recorded, so the write must not
    run (the success path would leave old workers nothing durable). The
    attempt cleans its OWN new-namespace marker and fails closed 503."""
    client1, client2, counters, fake_redis = two_workers
    claim = idem_module._distributed_claim
    claim._required = True
    key = "legacy-mark-dies-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    legacy_ns = IdempotencyMiddleware._namespace(1)

    real_eval = fake_redis.eval
    eval_calls = {"count": 0}

    def dying_eval(script, numkeys, key_, *args):
        if numkeys == 2:  # the intent-mark Lua
            eval_calls["count"] += 1
            if eval_calls["count"] == 2:
                # The SECOND mark is the legacy one.
                raise ConnectionError("simulated redis outage between marks")
        return real_eval(script, numkeys, key_, *args)

    monkeypatch.setattr(fake_redis, "eval", dying_eval)
    try:
        response = client1.post("/echo", headers=headers)
    finally:
        monkeypatch.undo()
        claim._required = False

    assert response.status_code == 503
    assert response.json()["code"] == "idempotency_unavailable"
    assert counters["w1"]["calls"] == 0, (
        "a required write never executes without its legacy migration guard"
    )
    assert nkey("1", key, "intent") not in fake_redis.store, (
        "the attempt cleaned its own new-namespace marker before the 503"
    )
    assert _legacy_nkey("1", key, "intent") not in fake_redis.store


def test_relinked_card_refused_after_invalid_key_flood(two_workers, monkeypatch):
    """THE round-7 owner P1 #2 scenario: success for card A, then a flood
    of INVALID keyed requests (the round-6 eviction vector — bindings were
    created before endpoint validation and NEVER released), then the
    account is re-linked to card B. The same key must refuse with 409
    idempotency_scope_mismatch and the handler must stay at ONE call.

    Round-7 fix (d): a known non-2xx DROPS its pre-handler binding (local +
    value-guarded Redis twin), so the flood cannot evict the durable
    successful binding that guards the live snapshot."""
    client1, client2, counters, fake_redis = two_workers
    from fastapi.responses import JSONResponse
    from fastapi.testclient import TestClient as TC

    monkeypatch.setattr(idem_module, "_MAX_SCOPE_BINDING_ENTRIES", 50)
    saved_policy = idem_module._patient_replay_policy_sync
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_claim = idem_module._distributed_claim
    idem_module._distributed_claim = _make_claim(fake_redis)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Patient", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id or 1
    )
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()

    counter = {"calls": 0}
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/booking-like")
    async def _booking_like(request: Request):
        if (request.headers.get("Idempotency-Key") or "").startswith("flood-"):
            return JSONResponse(
                status_code=422, content={"detail": {"reason": "invalid"}}
            )
        counter["calls"] += 1
        return {"ok": True}

    client = TC(app, raise_server_exceptions=False)
    origin_ns = IdempotencyMiddleware._namespace(1, "POST:/booking-like")
    key = "relink-flood-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    try:
        first = client.post("/booking-like", headers=headers)
        assert first.status_code == 200
        assert counter["calls"] == 1

        # The durable successful binding exists locally AND in Redis.
        assert (origin_ns, key) in idem_module._local_scope_bindings
        pscope_key = f"idem:{origin_ns}:{key}:pscope"
        assert fake_redis.store.get(pscope_key, "").startswith("patient:7|")

        # The flood: 120 unique keys that all end in a KNOWN non-2xx — 120
        # >> the 50-entry bound, the exact round-6 eviction vector.
        for i in range(120):
            flood = client.post(
                "/booking-like",
                headers={**auth_headers("1"), "Idempotency-Key": f"flood-{i}"},
            )
            assert flood.status_code == 422

        # Round-7 fix (d): the flood left NOTHING behind — every invalid
        # key's binding was dropped at its known outcome, so the durable
        # successful binding SURVIVED (round-6 LRU-evicted it here).
        assert (origin_ns, key) in idem_module._local_scope_bindings, (
            "the durable successful binding must survive an invalid-key flood"
        )
        assert not any(
            k[0] == origin_ns and k[1].startswith("flood-")
            for k in idem_module._local_scope_bindings
        ), "known non-2xx outcomes must not occupy binding slots"
        _leftover = [
            k
            for k in fake_redis.store
            if ":pscope" in k and k.split(":")[2].startswith("flood-")
        ]
        assert not _leftover, "the Redis twin bindings of the flood are dropped too"

        # The account is re-linked to card B; the same key must refuse.
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:8",
            False,
            True,
        )
        replay = client.post("/booking-like", headers=headers)
        assert replay.status_code == 409, replay.text
        assert replay.json()["code"] == "idempotency_scope_mismatch"
        assert counter["calls"] == 1, (
            "one logical submit — the re-linked card never gets a second record"
        )
        assert fake_redis.store.get(pscope_key, "").startswith("patient:7|")
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._distributed_claim = saved_claim
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()
        monkeypatch.undo()


def test_patient_outcome_replays_atomically_and_survives_local_eviction(
    two_workers, monkeypatch
):
    """Round-7 owner P1 #2 (fixes a+c): the LOCAL patient outcome is ONE
    atomic entry — binding + payload hash + snapshot, shared LRU fate — and
    the local replay path reads it directly. Even a FULL local eviction
    (binding AND snapshot gone together) never re-executes the write: the
    same-card retry replays from the durable Redis snapshot and the
    re-linked card is refused by the durable Redis binding."""
    client1, client2, counters, fake_redis = two_workers
    saved_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()
    key = "atomic-replay-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    origin_ns = IdempotencyMiddleware._namespace(1, "POST:/echo")
    try:
        first = client1.post("/echo", headers=headers)
        assert first.status_code == 200
        assert counters["w1"]["calls"] == 1

        # The atomic entry carries scope + snapshot (never a bare binding).
        entry = idem_module._local_scope_bindings.get((origin_ns, key))
        assert entry is not None and entry[1] == "patient:7"
        assert entry[2] is not None, "the snapshot is attached to the binding"

        # Same-card retry on a COLD worker replays through the distributed
        # snapshot (the local mirror is per-process by definition).
        replay = client2.post("/echo", headers=headers)
        assert replay.status_code == 200
        assert counters["w2"]["calls"] == 0

        # Simulate a FULL local eviction (the atomic entry removes scope
        # AND snapshot together — no orphaned response under a live key).
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()

        # The re-linked card is STILL refused — the durable Redis binding.
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:8",
            False,
            True,
        )
        relink = client2.post("/echo", headers=headers)
        assert relink.status_code == 409
        assert relink.json()["code"] == "idempotency_scope_mismatch"
        assert counters["w1"]["calls"] == 1 and counters["w2"]["calls"] == 0

        # And the SAME card replays from Redis — never re-executes.
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:7",
            False,
            True,
        )
        same_card = client2.post("/echo", headers=headers)
        assert same_card.status_code == 200
        assert counters["w2"]["calls"] == 0, (
            "eviction of the local mirror must not make a live outcome re-executable"
        )
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()


def test_scope_binding_store_stays_incremental_after_fill(monkeypatch):
    """Round-7 owner P2: after the bound is reached, set() stays O(1)-per-op
    — overflow is an immediate LRU popitem (no full sweep), expired entries
    are reclaimed incrementally through the lazy expiry heap, and the heap
    itself is compacted when stale records outgrow the live store."""
    monkeypatch.setattr(idem_module, "_MAX_SCOPE_BINDING_ENTRIES", 50)
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()
    saved_ttl = idem_module._CACHE_TTL_SECONDS
    try:
        # Expired entries are reclaimed INCREMENTALLY at the next set —
        # with an immediately-expiring TTL the very set() that wrote the
        # entry purges it again (no full sweep needed).
        idem_module._CACHE_TTL_SECONDS = -1
        idem_module._local_scope_binding_set("ns", "expired-1", "patient:1")
        assert ("ns", "expired-1") not in idem_module._local_scope_bindings, (
            "expired entries are reclaimed by the bounded-budget purge"
        )
        assert idem_module._local_scope_bindings_expiry == [], (
            "the heap record is pruned together with the entry"
        )
        idem_module._CACHE_TTL_SECONDS = saved_ttl

        # A flood of unique keys at the bound: the store stays bounded and
        # the heap is compacted to the live set (no stale-record growth).
        for i in range(300):
            idem_module._local_scope_binding_set("ns", f"f{i}", "patient:1")
        assert len(idem_module._local_scope_bindings) <= 50
        assert len(idem_module._local_scope_bindings_expiry) <= len(
            idem_module._local_scope_bindings
        ) + 64, "stale heap records are compacted once they outgrow the store"
        # The current record of a live entry is findable in the heap.
        _live_expires = idem_module._local_scope_bindings[("ns", "f299")][0]
        assert (_live_expires, ("ns", "f299")) in idem_module._local_scope_bindings_expiry
        # The newest entries are alive, the oldest evicted (LRU intact).
        assert idem_module._local_scope_binding_get("ns", "f0") is None
        assert idem_module._local_scope_binding_get("ns", "f299") == "patient:1"
    finally:
        idem_module._CACHE_TTL_SECONDS = saved_ttl
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()
        monkeypatch.undo()


def test_store_response_reports_confirmed_writes(fake_redis):
    """Round-7 (owner P1): store_response returns True only when Redis
    ANSWERED the SET; a degraded transport reports False instead of the
    old None-for-both contract."""
    import time as _time

    from fastapi import Response as FastAPIResponse

    claim = _make_claim(fake_redis)
    ok = claim.store_response(
        "ns-confirm",
        "k1",
        FastAPIResponse(content=b"{}", status_code=200),
        payload_hash="h",
        principal_role="Registrar",
    )
    assert ok is True
    assert fake_redis.store["idem:ns-confirm:k1:resp"]

    claim._available = False
    # Inside the reconnect cooldown: the probe is throttled and the degraded
    # transport must be REPORTED (False), never silently recovered.
    claim._failed_at = _time.time()
    degraded = claim.store_response(
        "ns-confirm",
        "k2",
        FastAPIResponse(content=b"{}", status_code=200),
    )
    assert degraded is False
    assert "idem:ns-confirm:k2:resp" not in fake_redis.store


def test_pre_deploy_legacy_outcome_replays_and_migrates(two_workers):
    """Rollout compatibility: the namespace became operation-scoped in
    #3340, but outcomes committed by the PREVIOUS deployment live under the
    user-only hash for up to 24h. A same-key retry after deploy must replay
    that committed outcome (never re-execute the write) and migrate it to
    the current namespace so later replays resolve without the legacy read."""
    from starlette.responses import Response

    client1, client2, counters, fake_redis = two_workers
    key = "legacy-outcome-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    # The pre-deploy worker committed and stored its outcome under the
    # user-only namespace, then died before the client saw the response.
    claim = idem_module._distributed_claim
    legacy_body = b'{"ok": true, "committed": "pre-deploy"}'
    claim.store_response(
        IdempotencyMiddleware._namespace(1),
        key,
        Response(
            content=legacy_body, status_code=200, media_type="application/json"
        ),
        payload_hash=idem_module.payload_hash(b""),
        principal_role="Registrar",
    )
    assert _legacy_nkey("1", key, "resp") in fake_redis.store

    # Post-deploy retry (fresh worker, cold local cache): the new namespace
    # has nothing — the legacy reconciliation must supply the outcome.
    replayed = client2.post("/echo", headers=headers)
    assert replayed.status_code == 200
    assert replayed.content == legacy_body, (
        "the pre-deploy committed outcome must replay, not re-execute"
    )
    assert counters["w2"]["calls"] == 0

    # Migration: the snapshot now lives under the CURRENT namespace too.
    assert nkey("1", key, "resp") in fake_redis.store, (
        "the legacy outcome must migrate so subsequent replays skip the legacy read"
    )


def test_pre_deploy_legacy_intent_refused_conservatively(two_workers):
    """A pre-deploy attempt that reached execution and died leaves an intent
    marker WITHOUT a stored outcome under the user-only namespace. The retry
    must reconcile (409 uncertain outcome) instead of blindly re-executing
    through the new namespace."""
    client1, client2, counters, fake_redis = two_workers
    key = "legacy-intent-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    claim = idem_module._distributed_claim
    confirmed = claim.mark_execution_intent(
        IdempotencyMiddleware._namespace(1), key
    )
    assert confirmed is True
    assert _legacy_nkey("1", key, "intent") in fake_redis.store

    retry = client2.post("/echo", headers=headers)
    assert retry.status_code == 409
    assert retry.json()["code"] == "idempotency_uncertain_outcome"
    assert counters["w2"]["calls"] == 0, (
        "the legacy unknown outcome must never re-execute the write"
    )


def test_pre_deploy_legacy_in_flight_claim_refused(two_workers):
    """Rolling deploy: the OLD worker is mid-execution when the retry lands
    on the NEW one. The legacy claim marker must refuse the retry (409
    in-flight) — its outcome surfaces under the legacy namespace when the
    old worker completes."""
    client1, client2, counters, fake_redis = two_workers
    key = "legacy-inflight-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    fake_redis.store[_legacy_nkey("1", key, "claim")] = uuid.uuid4().hex

    retry = client2.post("/echo", headers=headers)
    assert retry.status_code == 409
    assert retry.json()["code"] == "idempotency_in_flight"
    assert counters["w2"]["calls"] == 0


def test_patient_scope_principal_skips_legacy_reconciliation(two_workers):
    """Legacy snapshots carry no patient scope and cannot be attributed to
    the CURRENT card — replaying one across a re-link would resurrect the
    cross-card leak the patient-aware policy closed. Every patient-facing
    keyed endpoint is NEW in #3340, so patient-scope principals skip the
    legacy read entirely and execute fresh."""
    client1, client2, counters, fake_redis = two_workers
    key = "legacy-patient-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    # A hypothetical pre-deploy outcome under the user-only namespace.
    from starlette.responses import Response

    idem_module._distributed_claim.store_response(
        IdempotencyMiddleware._namespace(1),
        key,
        Response(content=b'{"committed": "pre-deploy"}', status_code=200),
        payload_hash=idem_module.payload_hash(b""),
        principal_role="Patient",
    )

    # This worker resolves an ACTIVE patient card (round-3 policy hook).
    saved_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:5",
        False,
        True,
    )
    try:
        fresh = client2.post("/echo", headers=headers)
    finally:
        idem_module._patient_replay_policy_sync = saved_policy

    assert fresh.status_code == 200
    assert fresh.json()["calls"] == 1, (
        "the legacy snapshot must NOT replay for a patient-scope principal"
    )
    assert counters["w2"]["calls"] == 1


def test_scope_binding_refuses_relinked_card_across_workers(two_workers):
    """Distributed scope binding: the key binds to the patient card it FIRST
    ran under (origin namespace = user + operation, no patient scope). A
    retry after the account was re-linked to another card is a 409
    idempotency_scope_mismatch — on ANY worker — never a second execution
    that would book the same attempt for a different patient."""
    client1, client2, counters, fake_redis = two_workers
    key = "scope-bind-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    saved_policy = idem_module._patient_replay_policy_sync
    try:
        # Card A: the booking commits, binding written (patient:7).
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:7",
            False,
            True,
        )
        first = client1.post("/echo", headers=headers)
        assert first.status_code == 200
        assert counters["w1"]["calls"] == 1
        # The binding lives under the ORIGIN namespace (no patient scope).
        origin_ns = IdempotencyMiddleware._namespace(1, "POST:/echo")
        assert fake_redis.store.get(
            f"idem:{origin_ns}:{key}:pscope", ""
        ).startswith("patient:7|")

        # The account is re-linked to card B; the retry (same key + body)
        # lands on ANOTHER worker — the binding refuses it there too.
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:8",
            False,
            True,
        )
        replay = client2.post("/echo", headers=headers)
        assert replay.status_code == 409, replay.text
        assert replay.json()["code"] == "idempotency_scope_mismatch"
        assert counters["w2"]["calls"] == 0
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()


# ── Round-5 (owner review on d4d160e, PR #3340) ─────────────────────────────


def test_pre_deploy_legacy_claim_and_intent_returns_in_flight(two_workers):
    """Round-5 owner P1: while an old worker EXECUTES, it holds BOTH legacy
    markers — the short in-flight claim AND the long-lived execution intent
    (written before the handler started). The retry must be refused as
    in-flight (retry the SAME key), never as uncertain-outcome (whose body
    advises a NEW key — following it duplicates the commit the old worker is
    about to land)."""
    client1, client2, counters, fake_redis = two_workers
    key = "legacy-inflight-both-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    # The pre-deploy worker is mid-execution: claim + intent both present.
    fake_redis.store[_legacy_nkey("1", key, "claim")] = uuid.uuid4().hex
    fake_redis.store[_legacy_nkey("1", key, "intent")] = uuid.uuid4().hex

    retry = client2.post("/echo", headers=headers)
    assert retry.status_code == 409, retry.text
    assert retry.json()["code"] == "idempotency_in_flight", (
        "an executing old worker must answer in-flight, not uncertain-outcome"
    )
    assert retry.headers.get("Retry-After") == "1"
    assert counters["w2"]["calls"] == 0

    # Once the old worker finished (claim gone, intent reconciled by its
    # stored outcome), the intent-only state reconciles conservatively.
    del fake_redis.store[_legacy_nkey("1", key, "claim")]
    from starlette.responses import Response

    idem_module._distributed_claim.store_response(
        IdempotencyMiddleware._namespace(1),
        key,
        Response(content=b'{"ok": true, "late": "old-worker"}', status_code=200),
        payload_hash=idem_module.payload_hash(b""),
        principal_role="Registrar",
    )
    # The stored outcome answers the retry (the uncertain intent is cleared
    # by the completing old worker); a bare intent would still reconcile.
    del fake_redis.store[_legacy_nkey("1", key, "intent")]
    final = client2.post("/echo", headers=headers)
    assert final.status_code == 200
    assert final.content == b'{"ok": true, "late": "old-worker"}'
    assert counters["w2"]["calls"] == 0


def _scope_get_failing_redis(fake: FakeRedis) -> FakeRedis:
    """Redis whose scope-binding GET fails while everything else (ping
    included) works — the 'dies ON the scope GET' window the round-5 owner
    review pinned for required coordination."""

    class _Failing(FakeRedis):
        def get(self, key: str) -> str | None:
            if key.endswith(":pscope"):
                raise ConnectionError("simulated scope-get failure")
            return super().get(key)

    failing = _Failing()
    failing.store = fake.store
    failing.ttls = fake.ttls
    failing.fail_next_ops = fake.fail_next_ops
    return failing


def test_required_redis_failure_on_scope_binding_refuses_503(monkeypatch):
    """Round-5 owner P1 (scenario A): required coordination passes the
    initial gate, then Redis fails ON the scope GET/SET. The binding state
    is UNKNOWN — the middleware must refuse 503 (non-executing) instead of
    inventing a local binding, and it must not leave a mirror binding for
    the refused request."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 60.0)
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_patient_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:5",
        False,
        True,
    )
    healthy = FakeRedis()
    claim = _make_claim(_scope_get_failing_redis(healthy))
    claim._required = True
    claim._lease_seconds = 90
    claim._failed_at = 0.0
    idem_module._distributed_claim = claim
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Patient", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id if user_id is not None else 9005
    )
    idem_module._local_scope_bindings.clear()
    try:
        counter = {"calls": 0}
        client = TestClient(_make_app(counter), raise_server_exceptions=False)
        h1 = auth_headers("1")
        r1 = client.post(
            "/echo", headers={**h1, "Idempotency-Key": "scope-fail-req-1"}
        )
        assert r1.status_code == 503, r1.text
        assert r1.json()["code"] == "idempotency_unavailable"
        assert counter["calls"] == 0, (
            "required coordination that fails on the binding must not execute"
        )
        assert not any(
            k[1] == "scope-fail-req-1" for k in idem_module._local_scope_bindings
        ), "the refused attempt must not leave a local binding for the key"
    finally:
        idem_module._distributed_claim = saved
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._patient_replay_policy_sync = saved_patient_policy
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._local_scope_bindings.clear()


def test_relinked_card_outage_refuses_via_mirrored_binding(two_workers, monkeypatch):
    """Round-5 owner P1 (scenario B): a Redis-resolved binding is MIRRORED
    into the per-process store, so a later outage still knows which card the
    key belongs to. A re-linked card retrying the same key during the outage
    gets 409 scope_mismatch — the previous code kept the Redis-only binding
    invisible to the mirror, re-bound the key to the NEW card and executed
    for it."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 60.0)
    import time as _time

    client1, client2, counters, fake_redis = two_workers
    key = "relink-outage-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    saved_policy = idem_module._patient_replay_policy_sync
    try:
        # Card A books with Redis up: binding lands in Redis AND the mirror.
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:7",
            False,
            True,
        )
        first = client1.post("/echo", headers=headers)
        assert first.status_code == 200
        assert counters["w1"]["calls"] == 1
        origin_ns = IdempotencyMiddleware._namespace(1, "POST:/echo")
        assert fake_redis.store.get(
            f"idem:{origin_ns}:{key}:pscope", ""
        ).startswith("patient:7|")
        assert any(
            k[1] == key for k in idem_module._local_scope_bindings
        ), "the Redis-resolved binding must be mirrored for outage resilience"

        # Redis outage on this worker (cooldown keeps it down for the retry).
        claim = idem_module._distributed_claim
        claim._available = False
        claim._failed_at = _time.time()

        # The account is re-linked to card B; the same key during the outage
        # must be refused by the MIRRORED binding — never re-bound.
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:8",
            False,
            True,
        )
        replay = client2.post("/echo", headers=headers)
        assert replay.status_code == 409, replay.text
        assert replay.json()["code"] == "idempotency_scope_mismatch"
        assert counters["w2"]["calls"] == 0
        # The binding was never re-written to card B.
        assert fake_redis.store.get(
            f"idem:{origin_ns}:{key}:pscope", ""
        ).startswith("patient:7|")
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()


def test_degraded_binding_unknown_scope_refuses_conservatively(two_workers, monkeypatch):
    """Round-5 owner P1 (fix 4): with degraded coordination and NO known
    binding, the key may be bound in Redis only (invisible while Redis is
    down). The attempt is refused conservatively — binding the key to the
    CURRENT card would execute a foreign attempt for a re-linked card."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 60.0)
    import time as _time

    client1, client2, counters, fake_redis = two_workers
    key = "degraded-unknown-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    saved_policy = idem_module._patient_replay_policy_sync
    try:
        idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
            "patient:9",
            False,
            True,
        )
        # Outage BEFORE any binding exists anywhere for this key.
        claim = idem_module._distributed_claim
        claim._available = False
        claim._failed_at = _time.time()

        response = client1.post("/echo", headers=headers)
        assert response.status_code == 503, response.text
        assert response.json()["code"] == "idempotency_unavailable"
        assert counters["w1"]["calls"] == 0, (
            "an unknown binding under degraded coordination must not execute"
        )
        assert not any(
            k[1] == key for k in idem_module._local_scope_bindings
        ), "the conservative refusal must not bind the key to the current card"
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()


def test_scope_binding_extend_is_value_guarded(fake_redis):
    """Round-5 owner P1 (fix 5) + Round-8 (owner P1 #2 + P2): the binding TTL
    is refreshed when the outcome is stored; the refresh is value-guarded
    (a foreign scope is never overwritten), carries the attempt generation
    and RESTORES an absent binding — a stale attempt's in-between cleanup
    can no longer orphan a successor's execution. The result is REPORTED
    (bool), and the known non-2xx cleanup is a FULL compare-and-delete of
    scope AND generation."""
    claim = _make_claim(fake_redis)
    claim._required = False
    claim._lease_seconds = 90
    claim._failed_at = 0.0
    origin_ns = "extend-ns"
    outcome, bound = claim.bind_scope_if_absent(
        origin_ns, "k-ext", "patient:1", "gen-a"
    )
    assert outcome == idem_module._SCOPE_BINDING_RESOLVED
    assert bound == "patient:1"
    scope_key = f"idem:{origin_ns}:k-ext:pscope"
    assert fake_redis.store[scope_key] == "patient:1|gen-a"

    # A foreign scope never overwrites the binding (and reports False).
    assert claim.extend_scope_binding(origin_ns, "k-ext", "patient:2", "gen-b") is False
    assert fake_redis.store[scope_key] == "patient:1|gen-a"
    # A prefix collision (patient:1 vs patient:12) must not pass the guard.
    fake_redis.store[f"idem:{origin_ns}:k-prefix:pscope"] = "patient:12|other"
    assert (
        claim.extend_scope_binding(origin_ns, "k-prefix", "patient:1", "gen-p")
        is False
    )
    assert fake_redis.store[f"idem:{origin_ns}:k-prefix:pscope"] == "patient:12|other"
    # Our own scope refresh re-stamps the generation and re-arms the TTL.
    assert claim.extend_scope_binding(origin_ns, "k-ext", "patient:1", "gen-b") is True
    assert fake_redis.store[scope_key] == "patient:1|gen-b"
    assert fake_redis.ttls[scope_key] == claim._ttl
    # Round-8: an ABSENT binding is RESTORED (never left missing while the
    # snapshot it guards is alive).
    del fake_redis.store[scope_key]
    assert claim.extend_scope_binding(origin_ns, "k-ext", "patient:1", "gen-c") is True
    assert fake_redis.store[scope_key] == "patient:1|gen-c"

    # The known non-2xx cleanup is a FULL compare-and-delete: only the
    # binding value THIS attempt wrote (scope AND generation) is removed.
    assert claim.clear_scope_binding(origin_ns, "k-ext", "patient:1", "gen-x") is False
    assert fake_redis.store[scope_key] == "patient:1|gen-c", (
        "a foreign generation never deletes the binding"
    )
    assert claim.clear_scope_binding(origin_ns, "k-ext", "patient:1", "gen-c") is True
    assert scope_key not in fake_redis.store

    # A legacy bare-scope value (no generation) still reads as the scope.
    fake_redis.store[f"idem:{origin_ns}:k-legacy:pscope"] = "patient:5"
    outcome, bound = claim.bind_scope_if_absent(
        origin_ns, "k-legacy", "patient:5", "gen-l"
    )
    assert outcome == idem_module._SCOPE_BINDING_RESOLVED and bound == "patient:5"


# ── Round-6 (owner review on 113d155, PR #3340): migration fence ────────────


def test_legacy_fence_blocks_old_worker_claiming_between_probe_and_new_acquire(
    two_workers, monkeypatch
):
    """THE rolling-deploy race the round-4/5 read-only probe could not close:
    the request of an OLD worker acquires the legacy claim AFTER the new
    worker's probe and starts executing, while the new worker acquires only
    the NEW-namespace claim — one logical write executed TWICE in parallel
    by two application versions.

    Round-6 fences FIRST: the legacy SET NX belongs to the new worker before
    it reads anything, so the old worker's claim attempt (emulated exactly at
    the old interleaving point — immediately before the new-namespace
    acquire) must FAIL and the old worker never executes."""
    client1, client2, counters, fake_redis = two_workers
    key = "fence-race-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    claim = idem_module._distributed_claim
    legacy_ns = IdempotencyMiddleware._namespace(1)
    legacy_claim_key = f"idem:{legacy_ns}:{key}:claim"

    real_acquire = DistributedIdempotencyClaim.acquire
    old_worker = {"claim_ok": None}

    def racing_acquire(self, user_id, k):
        if user_id != legacy_ns:
            # The old interleaving point: an old-version worker tries the
            # legacy claim right after the (round-4/5) probe and before the
            # new-namespace acquire.
            old_worker["claim_ok"] = fake_redis.set(
                legacy_claim_key, "old-worker-token", nx=True, ex=90
            )
        return real_acquire(self, user_id, k)

    monkeypatch.setattr(DistributedIdempotencyClaim, "acquire", racing_acquire)
    try:
        response = client1.post("/echo", headers=headers)
    finally:
        monkeypatch.undo()

    assert response.status_code == 200
    assert counters["w1"]["calls"] == 1, "only the NEW worker executes"
    assert old_worker["claim_ok"] is None, (
        "the legacy fence must be held by THIS worker at the moment the old "
        "worker would claim the legacy namespace — the old worker's SET NX "
        "must fail (no parallel old/new execution of one key)"
    )
    # The fence is released after completion (compare-and-delete) and the
    # outcome is DUAL-WRITTEN to the legacy namespace for old workers.
    assert legacy_claim_key not in fake_redis.store
    assert _legacy_nkey("1", key, "resp") in fake_redis.store


def test_legacy_outcome_landing_between_fence_and_probe_replays(
    two_workers, monkeypatch
):
    """The second round-4/5 hole: the old worker completes BETWEEN the three
    separate probe GETs — the response read saw nothing, by the marker reads
    the response was stored and the markers dropped → three misses and the
    write re-executed. Round-6 reads the legacy artifacts only AFTER owning
    the fence: an old worker completing in that window is REPLAYED and
    migrated, never re-executed."""
    client1, client2, counters, fake_redis = two_workers
    key = "fence-complete-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    claim = idem_module._distributed_claim
    legacy_ns = IdempotencyMiddleware._namespace(1)

    from starlette.responses import Response as StarletteResponse

    real_probe = DistributedIdempotencyClaim.probe_legacy_artifacts

    def completing_old_worker_probe(self, ns, k):
        if ns == legacy_ns and k == key:
            # The old worker finishes EXACTLY between the fence and the
            # probe: its committed outcome lands in the legacy namespace.
            claim.store_response(
                legacy_ns,
                k,
                StarletteResponse(
                    content=b'{"ok": true, "committed": "old-worker"}',
                    status_code=200,
                    media_type="application/json",
                ),
                payload_hash=idem_module.payload_hash(b""),
                principal_role="Registrar",
            )
        return real_probe(self, ns, k)

    monkeypatch.setattr(
        DistributedIdempotencyClaim, "probe_legacy_artifacts", completing_old_worker_probe
    )
    try:
        response = client1.post("/echo", headers=headers)
    finally:
        monkeypatch.undo()

    assert response.status_code == 200
    assert response.content == b'{"ok": true, "committed": "old-worker"}'
    assert counters["w1"]["calls"] == 0, (
        "the just-completed legacy outcome must replay, never re-execute"
    )
    # Migrated to the current namespace; the fence is released.
    assert nkey("1", key, "resp") in fake_redis.store
    assert f"idem:{legacy_ns}:{key}:claim" not in fake_redis.store


def test_fence_dual_writes_outcome_to_legacy_namespace(two_workers):
    """Round-6 requirement: the committed outcome is DUAL-WRITTEN to BOTH
    namespaces while the fence is held and released only after the write —
    an old-version worker that acquires the legacy claim after the fence
    lease lapses must find the snapshot and replay, never an empty legacy
    namespace it would re-execute."""
    client1, client2, counters, fake_redis = two_workers
    key = "dual-write-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    claim = idem_module._distributed_claim
    legacy_ns = IdempotencyMiddleware._namespace(1)

    first = client1.post("/echo", headers=headers)
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    assert _legacy_nkey("1", key, "resp") in fake_redis.store, (
        "the outcome must be dual-written to the legacy namespace"
    )
    assert f"idem:{legacy_ns}:{key}:claim" not in fake_redis.store, (
        "the fence must be released after completion"
    )
    # Round-7 (owner P1): the pre-handler LEGACY intent (written under the
    # fence before execution) is cleared together with the new-namespace
    # marker once the outcome is CONFIRMED durable in both namespaces.
    assert _legacy_nkey("1", key, "intent") not in fake_redis.store, (
        "the pre-handler legacy intent is cleared after the confirmed dual-write"
    )
    assert nkey("1", key, "intent") not in fake_redis.store
    # The dual-written snapshot replays under the SAME replay contract the
    # legacy read applies (load_response reads the legacy namespace).
    replayed, stored_hash, stored_role = claim.load_response(legacy_ns, key)
    assert replayed is not None
    assert stored_hash == idem_module.payload_hash(b"")
    assert stored_role == "Registrar"


def test_crash_dual_writes_legacy_intent_and_keeps_fence(two_workers):
    """A crash AFTER execution started leaves the outcome unknown. The NEW
    claim is released (the retry reconciles via the new-namespace intent),
    the legacy fence is KEPT (it lapses with its own lease) and an
    unknown-outcome intent is DUAL-WRITTEN to the legacy namespace — an
    old-version worker must reconcile (409 uncertain), never re-execute a
    possibly-committed write once the fence lease lapses."""
    client1, client2, counters, fake_redis = two_workers
    key = "dual-crash-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    legacy_ns = IdempotencyMiddleware._namespace(1)

    first = client1.post("/boom", headers=headers)
    assert first.status_code == 500

    assert nkey("1", key, "claim", path="/boom") not in fake_redis.store, (
        "the new-namespace claim is released on crash (R9 contract)"
    )
    assert f"idem:{legacy_ns}:{key}:intent" in fake_redis.store, (
        "the unknown-outcome intent must be dual-written to the legacy namespace"
    )
    assert f"idem:{legacy_ns}:{key}:claim" in fake_redis.store, (
        "the legacy fence stays held after a crash (lapses with its lease)"
    )


def test_required_redis_death_at_fence_returns_503(two_workers, monkeypatch):
    """Coordination REQUIRED dies between the initial availability gate and
    the fence acquire: acquire() returns None because of the transport
    failure, not because of contention — the honest answer is the
    non-executing 503 (Retry-After 2), never a misleading 409 and never a
    local execution."""
    client1, client2, counters, fake_redis = two_workers
    claim = idem_module._distributed_claim
    claim._required = True
    key = "fence-503-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    def dying_set(*args, **kwargs):
        raise ConnectionError("simulated redis outage")

    monkeypatch.setattr(fake_redis, "set", dying_set)
    try:
        response = client1.post("/echo", headers=headers)
    finally:
        monkeypatch.undo()
        claim._required = False

    assert response.status_code == 503
    assert response.json()["code"] == "idempotency_unavailable"
    assert counters["w1"]["calls"] == 0


# ── Round-6 (owner review on 113d155, PR #3340): key bound + bounded mirror ─


def test_oversized_key_rejected_400_before_any_allocation(two_workers):
    """Round-6 owner P1: the Idempotency-Key header is caller-owned — an
    oversized key is refused NON-EXECUTING (400 idempotency_key_invalid)
    BEFORE the body read, principal resolution, Redis keys or the scope
    mirror allocate anything. 128 chars exactly is accepted."""
    client1, client2, counters, fake_redis = two_workers
    idem_module._local_scope_bindings.clear()

    response = client1.post(
        "/echo",
        headers={**auth_headers("1"), "Idempotency-Key": "k" * 129},
    )
    assert response.status_code == 400
    assert response.json()["code"] == "idempotency_key_invalid"
    assert counters["w1"]["calls"] == 0
    assert fake_redis.store == {}, "no Redis state may be created for a refused key"
    assert not idem_module._local_scope_bindings, "no mirror entry for a refused key"

    ok = client1.post(
        "/echo", headers={**auth_headers("1"), "Idempotency-Key": "k" * 128}
    )
    assert ok.status_code == 200, "the boundary length itself is valid"


def test_local_scope_bindings_bounded_lru(monkeypatch):
    """Round-6 owner P1: the process-local scope-binding mirror is
    attacker-reachable (every fresh keyed request writes an entry BEFORE
    endpoint validation), so it must be a BOUNDED LRU: a flood of unique
    keys evicts its own oldest entries instead of growing without limit,
    and recently used entries survive. Round-7: entries are ATOMIC
    (scope + payload hash + snapshot) and a known non-2xx DROPS its
    binding instead of occupying a slot for 24 h."""
    import time as _time

    monkeypatch.setattr(idem_module, "_MAX_SCOPE_BINDING_ENTRIES", 50)
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()
    try:
        for i in range(120):
            idem_module._local_scope_binding_set("ns", f"k{i}", "patient:1")
        assert len(idem_module._local_scope_bindings) <= 50
        # Oldest entries evicted, newest present.
        assert idem_module._local_scope_binding_get("ns", "k0") is None
        assert idem_module._local_scope_binding_get("ns", "k119") == "patient:1"
        # LRU: a GET makes the entry recent; later inserts must not evict it.
        assert idem_module._local_scope_binding_get("ns", "k100") == "patient:1"
        for i in range(120, 160):
            idem_module._local_scope_binding_set("ns", f"k{i}", "patient:2")
        assert idem_module._local_scope_binding_get("ns", "k100") == "patient:1", (
            "a recently used binding must survive LRU eviction"
        )
        assert len(idem_module._local_scope_bindings) <= 50

        # Round-7: the outcome is stored ATOMICALLY with the binding —
        # one entry carries scope + payload hash + snapshot (shared LRU
        # fate), and the get helper reconstructs the replay contract view.
        from fastapi import Response as FastAPIResponse

        outcome = FastAPIResponse(
            content=b'{"ok": true}', status_code=200, media_type="application/json"
        )
        idem_module._local_patient_outcome_store(
            "ns", "atomic-1", "patient:3", outcome, "hash-1", "Patient"
        )
        entry = idem_module._local_scope_bindings[("ns", "atomic-1")]
        assert entry[1] == "patient:3"
        assert entry[2] is not None and entry[2][4] == "hash-1"
        replayed, mismatch, role = idem_module._local_patient_outcome_get(
            "ns", "atomic-1", "hash-1"
        )
        assert replayed is not None and replayed.status_code == 200
        assert mismatch is False and role == "Patient"
        changed, mismatch, _role = idem_module._local_patient_outcome_get(
            "ns", "atomic-1", "hash-2"
        )
        assert changed is not None and mismatch is True, (
            "a changed payload is flagged from the atomic snapshot"
        )

        # Value-guarded drop (known non-2xx): our own binding is removed,
        # a foreign one is never touched.
        idem_module._local_scope_binding_drop("ns", "atomic-1", "patient:9")
        assert ("ns", "atomic-1") in idem_module._local_scope_bindings
        idem_module._local_scope_binding_drop("ns", "atomic-1", "patient:3")
        assert ("ns", "atomic-1") not in idem_module._local_scope_bindings

        # Snapshot-only forget (role-changed re-execution): the binding
        # survives, the snapshot is gone; a foreign scope is never touched.
        idem_module._local_scope_binding_set("ns", "forget-1", "patient:4")
        idem_module._local_patient_outcome_forget_snapshot("ns", "forget-1", "patient:9")
        assert ("ns", "forget-1") in idem_module._local_scope_bindings, (
            "a foreign scope never rewrites the entry"
        )
        idem_module._local_patient_outcome_forget_snapshot("ns", "forget-1", "patient:4")
        assert idem_module._local_scope_bindings[("ns", "forget-1")][2] is None
        assert (
            idem_module._local_scope_bindings[("ns", "forget-1")][0]
            > _time.time() + idem_module._CACHE_TTL_SECONDS - 1
        ), "the binding TTL is refreshed on the snapshot forget"
    finally:
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()
        monkeypatch.undo()


def test_local_only_binding_outlives_response_snapshot(two_workers, monkeypatch):
    """Round-6 owner P2: in a LOCAL-ONLY deployment (no distributed claim)
    the binding is written BEFORE the handler while the response snapshot is
    cached AFTER it — with the same 24h TTL the binding always expired
    FIRST, and a retry inside that window re-bound the key to a re-linked
    card and executed a second write. The binding must be refreshed on the
    SAME instant the response snapshot is stored."""
    saved_claim = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
    saved_policy = idem_module._patient_replay_policy_sync
    idem_module._distributed_claim = None
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Patient", False)
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id or 1
    )
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    idem_module._local_scope_bindings.clear()

    from fastapi import FastAPI
    from fastapi.testclient import TestClient as TC

    key = "local-extend-1"
    origin_ns = IdempotencyMiddleware._namespace(1, "POST:/booking-like")
    seen = {}

    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/booking-like")
    async def _booking_like():
        # Capture the binding expiry DURING the handler (before the
        # response snapshot is stored).
        entry = idem_module._local_scope_bindings.get((origin_ns, key))
        seen["during"] = entry[0] if entry else None
        return {"ok": True}

    client = TC(app, raise_server_exceptions=False)
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    try:
        first = client.post("/booking-like", headers=headers)
        assert first.status_code == 200
        entry = idem_module._local_scope_bindings.get((origin_ns, key))
        assert entry is not None, "the binding is mirrored locally"
        assert seen["during"] is not None, "the binding existed before the handler"
        assert entry[0] > seen["during"], (
            "the binding expiry must be REFRESHED at response-store time — "
            "it may never expire before the snapshot it guards"
        )

        # Same-key retry replays the local snapshot (binding intact).
        second = client.post("/booking-like", headers=headers)
        assert second.status_code == 200
    finally:
        idem_module._distributed_claim = saved_claim
        idem_module._check_principal_authorized_sync = saved_auth
        idem_module._resolve_principal_id_sync = saved_resolve
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()


# ── Round-8 (owner review on 5fb7a23, PR #3340) ─────────────────────────────


def test_redis_scope_mirror_preserves_local_snapshot(two_workers, monkeypatch):
    """THE round-8 owner P1 scenario: a same-key retry whose Redis scope GET
    succeeds must not wipe the locally stored response snapshot. The mirror
    used to replace the whole atomic entry with snapshot=None; when Redis
    then refused the response GET, the local outcome was gone and the next
    degraded retry re-executed the handler (a second booking)."""
    client1, client2, counters, fake_redis = two_workers
    saved_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()
    key = "mirror-snapshot-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    origin_ns = IdempotencyMiddleware._namespace(1, "POST:/echo")
    try:
        first = client1.post("/echo", headers=headers)
        assert first.status_code == 200
        assert counters["w1"]["calls"] == 1
        entry = idem_module._local_scope_bindings.get((origin_ns, key))
        assert entry is not None and entry[2] is not None, (
            "the atomic entry carries the binding AND the snapshot"
        )

        # Redis answers the scope GET but refuses the response GET — the
        # exact ordering that made the erased snapshot unrecoverable.
        real_get = fake_redis.get

        def scope_ok_resp_dead(key_, *a, **kw):
            if key_.endswith(":resp"):
                raise ConnectionError("simulated response GET failure")
            return real_get(key_, *a, **kw)

        monkeypatch.setattr(fake_redis, "get", scope_ok_resp_dead)
        replay = client1.post("/echo", headers=headers)
        assert replay.status_code == 200
        assert replay.json()["calls"] == 1
        assert counters["w1"]["calls"] == 1, (
            "the local atomic snapshot must survive the Redis scope mirror — "
            "the same-key retry replays locally, never re-executes"
        )
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()
        monkeypatch.undo()


def test_non_2xx_binding_cleanup_precedes_claim_release(two_workers, monkeypatch):
    """THE round-8 owner P1 #2 race: attempt A returns a known 400; a
    successor B with the same key and a corrected body must not be able to
    start executing while A is still deleting 'its' scope binding (A and B
    share the patient scope, so only the cleanup ORDER plus the generation
    compare-and-delete protect B). While A is frozen before its binding
    cleanup, B is refused in-flight; after A completes, its own generation
    binding is gone; B's retry executes and its Redis binding REMAINS, so a
    re-linked card is refused 409 scope_mismatch with the handler at ONE
    successful call."""
    client1, client2, counters, fake_redis = two_workers
    saved_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()

    counter = {"calls": 0}
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/booking-like")
    async def _booking_like(request: Request):
        body = await request.body()
        if b"invalid" in body:
            from fastapi.responses import JSONResponse

            return JSONResponse(
                status_code=400, content={"detail": "validation failed"}
            )
        counter["calls"] += 1
        return {"ok": True}

    from fastapi.testclient import TestClient as TC

    worker_a = TC(app, raise_server_exceptions=False)
    worker_b = TC(app, raise_server_exceptions=False)
    origin_ns = IdempotencyMiddleware._namespace(1, "POST:/booking-like")
    pscope_key = f"idem:{origin_ns}:cleanup-order-1:pscope"
    a_headers = {
        **auth_headers("1"),
        "Idempotency-Key": "cleanup-order-1",
        "Content-Type": "application/json",
    }
    b_headers = {
        **auth_headers("1"),
        "Idempotency-Key": "cleanup-order-1",
        "Content-Type": "application/json",
    }

    pause_a = threading.Event()
    resume_a = threading.Event()

    real_clear = DistributedIdempotencyClaim.clear_scope_binding

    def pausing_clear(self, o_ns, k, scope, generation):
        pause_a.set()
        resume_a.wait(5)
        return real_clear(self, o_ns, k, scope, generation)

    monkeypatch.setattr(DistributedIdempotencyClaim, "clear_scope_binding", pausing_clear)
    try:
        a_result = {}

        def _a_attempt():
            a_result["resp"] = worker_a.post(
                "/booking-like", headers=a_headers, content=b"invalid"
            )

        ta = threading.Thread(target=_a_attempt)
        ta.start()
        assert pause_a.wait(5), "A must reach its binding cleanup"
        assert fake_redis.store.get(pscope_key, "").startswith("patient:7|"), (
            "the binding still exists while A is frozen before the cleanup"
        )

        # B (corrected body) arrives while A is mid-cleanup: the claim is
        # still held, so B must be refused in-flight — never started.
        b_result = {}

        def _b_attempt():
            b_result["resp"] = worker_b.post(
                "/booking-like", headers=b_headers, content=b"{}"
            )

        tb = threading.Thread(target=_b_attempt)
        tb.start()
        tb.join(10)
        assert b_result["resp"].status_code == 409, b_result["resp"].text
        assert b_result["resp"].json()["code"] == "idempotency_in_flight"
        assert counter["calls"] == 0

        resume_a.set()
        ta.join(10)
        assert a_result["resp"].status_code == 400
        # A's own generation was compare-and-deleted.
        assert pscope_key not in fake_redis.store
    finally:
        resume_a.set()
        monkeypatch.undo()
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()

    # B retries with the corrected body — binding absent, it re-binds and
    # executes; its completed outcome re-stamps the binding (generation B).
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    retry = worker_b.post("/booking-like", headers=b_headers, content=b"{}")
    assert retry.status_code == 200
    assert counter["calls"] == 1
    assert fake_redis.store.get(pscope_key, "").startswith("patient:7|"), (
        "the Redis origin binding must REMAIN after B's success"
    )

    # The re-linked card never re-runs the key.
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:8",
        False,
        True,
    )
    try:
        relinked = worker_b.post("/booking-like", headers=b_headers, content=b"{}")
        assert relinked.status_code == 409
        assert relinked.json()["code"] == "idempotency_scope_mismatch"
        assert counter["calls"] == 1, "one logical submit — never a second record"
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()


def test_store_response_with_scope_atomic_contract(fake_redis):
    """Round-8 (owner P2): the atomic store+scope script reports BOTH facts —
    (True, True) confirmed; (True, False) foreign-scope binding (the
    response lands, the binding is never overwritten, the outcome is NOT
    durable); (False, False) degraded transport (nothing lands). The
    binding is RESTORED when absent and refreshed with the generation."""
    import time as _time

    from fastapi import Response as FastAPIResponse

    claim = _make_claim(fake_redis)
    resp = FastAPIResponse(content=b"{}", status_code=201)
    ok, ext = claim.store_response_with_scope(
        "rns",
        "k1",
        resp,
        origin_ns="ons",
        patient_scope="patient:1",
        generation="g1",
    )
    assert ok is True and ext is True
    assert "idem:rns:k1:resp" in fake_redis.store
    assert fake_redis.store["idem:ons:k1:pscope"] == "patient:1|g1"
    assert fake_redis.ttls["idem:ons:k1:pscope"] == claim._ttl

    # Foreign scope: response stored, binding untouched, NOT durable.
    fake_redis.store["idem:ons:k2:pscope"] = "patient:9|foreign"
    ok2, ext2 = claim.store_response_with_scope(
        "rns",
        "k2",
        resp,
        origin_ns="ons",
        patient_scope="patient:1",
        generation="g2",
    )
    assert ok2 is True and ext2 is False
    assert fake_redis.store["idem:ons:k2:pscope"] == "patient:9|foreign"

    # Prefix collision must not pass the value guard (patient:1 vs patient:12).
    fake_redis.store["idem:ons:k3:pscope"] = "patient:12|other"
    ok3, ext3 = claim.store_response_with_scope(
        "rns",
        "k3",
        resp,
        origin_ns="ons",
        patient_scope="patient:1",
        generation="g3",
    )
    assert ok3 is True and ext3 is False
    assert fake_redis.store["idem:ons:k3:pscope"] == "patient:12|other"

    # Absent binding is RESTORED atomically with the response.
    del fake_redis.store["idem:ons:k1:pscope"]
    ok4, ext4 = claim.store_response_with_scope(
        "rns",
        "k1",
        resp,
        origin_ns="ons",
        patient_scope="patient:1",
        generation="g4",
    )
    assert ok4 is True and ext4 is True
    assert fake_redis.store["idem:ons:k1:pscope"] == "patient:1|g4"

    # Degraded transport reports (False, False) and stores NOTHING.
    claim._available = False
    claim._failed_at = _time.time()
    ok5, ext5 = claim.store_response_with_scope(
        "rns",
        "k5",
        resp,
        origin_ns="ons",
        patient_scope="patient:1",
        generation="g5",
    )
    assert ok5 is False and ext5 is False
    assert "idem:rns:k5:resp" not in fake_redis.store


def test_scope_extension_failure_keeps_outcome_non_durable(two_workers, monkeypatch):
    """Round-8 owner P2: a Redis failure on the atomic response+scope store
    means the patient outcome is NOT durable — the 2xx still reaches the
    client (the write IS committed) but every unknown-outcome guard stays
    up, and the same-key retry reconciles (409 uncertain_outcome) instead
    of replaying a snapshot whose binding was never confirmed."""
    client1, client2, counters, fake_redis = two_workers
    saved_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()
    key = "extend-dead-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    origin_ns = IdempotencyMiddleware._namespace(1, "POST:/echo")
    # The outcome namespace of a patient-scope request carries the card
    # scope (resp/intent), unlike the ORIGIN namespace (pscope).
    scoped_ns = IdempotencyMiddleware._namespace(1, "POST:/echo", "patient:7")

    real_eval = fake_redis.eval

    def dying_eval(script, numkeys, *keys_and_args):
        if "-- store+scope" in script:
            raise ConnectionError("simulated redis outage at store+scope")
        return real_eval(script, numkeys, *keys_and_args)

    monkeypatch.setattr(fake_redis, "eval", dying_eval)
    try:
        first = client1.post("/echo", headers=headers)
        assert first.status_code == 200
        assert counters["w1"]["calls"] == 1
        # The atomic script never ran: no snapshot landed…
        assert f"idem:{scoped_ns}:{key}:resp" not in fake_redis.store
        # …the pre-handler binding exists but was never extended, and the
        # unknown-outcome guards stay up.
        assert fake_redis.store.get(f"idem:{origin_ns}:{key}:pscope", "").startswith(
            "patient:7|"
        )
        assert f"idem:{scoped_ns}:{key}:intent" in fake_redis.store
    finally:
        monkeypatch.undo()
        idem_module._patient_replay_policy_sync = saved_policy

    # The client that lost the response retries from a cold worker. The
    # degraded release could not drop the in-flight claim (cooldown), so the
    # first retry is refused in-flight; once the lease lapses (simulated),
    # the KEPT intent reconciles the retry (409 uncertain) — the handler
    # never re-runs the committed write.
    claim = idem_module._distributed_claim
    claim._available = True
    claim._failed_at = 0.0
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()
    saved_policy = idem_module._patient_replay_policy_sync
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        "patient:7",
        False,
        True,
    )
    try:
        retry = client2.post("/echo", headers=headers)
        assert retry.status_code == 409
        assert retry.json()["code"] == "idempotency_in_flight"
        assert counters["w1"]["calls"] == 1 and counters["w2"]["calls"] == 0

        # The leases lapse (the claim TTL simulated away) — the exact
        # post-lease moment: the intent WITHOUT a response reconciles.
        del fake_redis.store[f"idem:{scoped_ns}:{key}:claim"]
        late_retry = client2.post("/echo", headers=headers)
        assert late_retry.status_code == 409
        assert late_retry.json()["code"] == "idempotency_uncertain_outcome"
        assert counters["w1"]["calls"] == 1 and counters["w2"]["calls"] == 0, (
            "a non-durable outcome keeps the unknown-outcome guard up — "
            "the committed write is never re-run"
        )
    finally:
        idem_module._patient_replay_policy_sync = saved_policy
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()


def test_staff_same_key_two_operations_execute_independently(two_workers):
    """Round-8 owner P2: the user-only legacy namespace must not alias two
    different POST operations that share one Idempotency-Key. /echo's
    committed snapshot (stamped POST:/echo) is neither replayed nor
    mismatch-refused for /cart-like — both operations execute."""
    client1, client2, counters, fake_redis = two_workers
    key = "cross-op-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    first = client1.post("/echo", headers=headers)
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1
    # The dual-written legacy snapshot carries the operation stamp.
    legacy_raw = fake_redis.store[_legacy_nkey("1", key, "resp")]
    assert json.loads(legacy_raw)["operation_scope"] == "POST:/echo"

    second = client2.post("/cart-like", headers=headers)
    assert second.status_code == 200, second.text
    assert counters["w2"]["calls"] == 1, (
        "the other operation must EXECUTE — a foreign-operation snapshot is "
        "neither replayed nor refused as a payload mismatch"
    )


def test_legacy_bridge_cutoff_disables_user_only_writes(two_workers, monkeypatch):
    """Round-8 owner P2: after the rollout window the user-only bridge is
    dead — no fence, no probe, no dual-write; the operation-scoped namespace
    is the only truth and same-key retries replay from it."""
    client1, client2, counters, fake_redis = two_workers
    key = "bridge-cutoff-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    monkeypatch.setattr(idem_module, "_legacy_bridge_active", lambda: False)
    try:
        first = client1.post("/echo", headers=headers)
        assert first.status_code == 200
        assert counters["w1"]["calls"] == 1
        assert _legacy_nkey("1", key, "resp") not in fake_redis.store, (
            "no legacy dual-write after the cutoff"
        )
        assert _legacy_nkey("1", key, "claim") not in fake_redis.store, (
            "no legacy fence after the cutoff"
        )
        assert _legacy_nkey("1", key, "intent") not in fake_redis.store, (
            "no legacy intent after the cutoff"
        )
        replay = client2.post("/echo", headers=headers)
        assert replay.status_code == 200
        assert counters["w2"]["calls"] == 0, (
            "same-key retries replay from the operation-scoped namespace"
        )
    finally:
        monkeypatch.undo()


def test_legacy_intent_lost_ack_cleaned_by_owner(two_workers, monkeypatch):
    """Round-8 owner P2: the pre-handler legacy intent EVAL may LAND
    server-side while the client loses the reply (confirmed=False covers
    both 'not written' and 'written, response lost'). The fail-close branch
    must owner-clean the landed marker (fence-token compare-and-delete) so
    a request that provably never executed does not hold a false 24h
    idempotency_uncertain_outcome."""
    client1, client2, counters, fake_redis = two_workers
    claim = idem_module._distributed_claim
    claim._required = True
    key = "legacy-lost-ack-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}

    real_eval = fake_redis.eval
    eval_calls = {"count": 0}

    def lost_ack_eval(script, numkeys, *keys_and_args):
        result = real_eval(script, numkeys, *keys_and_args)
        if numkeys == 2 and "KEYS[2]" in script and "store+scope" not in script:
            eval_calls["count"] += 1
            if eval_calls["count"] == 2:
                # The SECOND intent mark is the legacy one: the marker IS
                # in the store, but the client's reply is lost.
                raise ConnectionError("simulated lost ack on legacy intent mark")
        return result

    monkeypatch.setattr(fake_redis, "eval", lost_ack_eval)
    try:
        response = client1.post("/echo", headers=headers)
    finally:
        monkeypatch.undo()
        claim._required = False

    assert response.status_code == 503
    assert response.json()["code"] == "idempotency_unavailable"
    assert counters["w1"]["calls"] == 0, "the handler never ran"
    assert _legacy_nkey("1", key, "intent") not in fake_redis.store, (
        "the landed-but-unacknowledged OWN legacy intent is cleaned"
    )
    assert nkey("1", key, "intent") not in fake_redis.store, (
        "the own new-namespace marker is cleaned too"
    )
    # The in-flight markers (claim + fence) are released best-effort through
    # the reconnect cooldown — here the cooldown holds, so they lapse with
    # their 90 s leases instead; the key stays blocked for seconds, which is
    # the documented fail-closed contract for a degraded required attempt.

    # After recovery the same key executes normally — no false reconcile.
    retry = client2.post("/echo", headers=headers)
    assert retry.status_code == 200
    assert counters["w2"]["calls"] == 1


# ── Round-9 (owner P1/P2, PR #3340) ─────────────────────────────────────────


class _ReassertScenarioRedis(FakeRedis):
    """Round-9 harness: intervenes at the POST-ACQUIRE scope re-assert —
    the FIRST ``scope-upsert`` eval of a patient dispatch. The pre-handler
    bind uses plain GET/SET NX, so the re-assert is exactly the first
    Lua upsert a patient attempt executes. The hook fires ONCE; later
    upserts (the recovered retry, the success-path store) pass through."""

    def __init__(self) -> None:
        super().__init__()
        self.reassert_seen = False

    def _on_reassert(self, scope_key: str) -> None:
        """Hook for the scenario (raise or tamper)."""

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> int:
        if "scope-upsert" in script and not self.reassert_seen:
            self.reassert_seen = True
            self._on_reassert(keys_and_args[0])
        return super().eval(script, numkeys, *keys_and_args)


class _TransportDownAtReassertRedis(_ReassertScenarioRedis):
    """The re-assert EVAL dies on the transport: the scope cannot be
    confirmed on the very last check before the business write."""

    def _on_reassert(self, scope_key: str) -> None:
        raise ConnectionError("simulated transport failure on scope re-assert")


class _RelinkedAtReassertRedis(_ReassertScenarioRedis):
    """Between the successor's acquire and its re-assert, the origin
    binding was re-bound to ANOTHER card (the stale-cleanup/relink race).
    The upsert then correctly refuses to touch the foreign binding."""

    def _on_reassert(self, scope_key: str) -> None:
        self.store[scope_key] = "patient:99|stale-attempt"


def _install_patient_worker(monkeypatch, fake_redis, patient_scope: str = "patient:7"):
    """Wire ONE harness worker with a patient-scoped policy (round-7 test
    pattern): saves and restores every singleton the dispatch reads."""
    saved = (
        idem_module._distributed_claim,
        idem_module._check_principal_authorized_sync,
        idem_module._resolve_principal_id_sync,
        idem_module._patient_replay_policy_sync,
    )
    idem_module._distributed_claim = _make_claim(fake_redis)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (
        True,
        "Patient",
        False,
    )
    idem_module._resolve_principal_id_sync = lambda request, user_id, username: (
        user_id or 1
    )
    idem_module._patient_replay_policy_sync = lambda request, canonical_id: (
        patient_scope,
        False,
        True,
    )
    idem_module._local_scope_bindings.clear()
    idem_module._local_scope_bindings_expiry.clear()
    counter = {"calls": 0}

    def _restore():
        (
            idem_module._distributed_claim,
            idem_module._check_principal_authorized_sync,
            idem_module._resolve_principal_id_sync,
            idem_module._patient_replay_policy_sync,
        ) = saved
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()

    return counter, _restore


def test_scope_reassert_transport_failure_fails_closed_503(monkeypatch):
    """Round-9 owner P1 (mandatory concurrency test): B acquires the claim,
    then Redis dies ON the scope re-assert. The unconfirmed scope must NOT
    let the endpoint run: handler calls = 0, answer 503
    idempotency_unavailable. After recovery the SAME key executes normally
    (the refused attempt left neither intent nor outcome behind)."""

    fake = _TransportDownAtReassertRedis()
    counter, restore = _install_patient_worker(monkeypatch, fake)
    from fastapi.testclient import TestClient as TC

    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/booking-like")
    async def _booking_like() -> dict[str, Any]:
        counter["calls"] += 1
        return {"ok": True}

    client = TC(app, raise_server_exceptions=False)
    key = "reassert-503-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    try:
        first = client.post("/booking-like", headers=headers)
        assert first.status_code == 503, first.text
        assert first.json()["code"] == "idempotency_unavailable"
        assert counter["calls"] == 0, "an unconfirmed scope never runs the handler"

        # Recovery: the reconnect cooldown elapses and the lease of the
        # released-but-unreachable claim lapses. The re-assert hook is a
        # one-shot — the recovered retry's own upsert passes through.
        claim = idem_module._distributed_claim
        claim._available = True
        claim._failed_at = 0.0
        # The claim (and intent) namespaces carry the PATIENT scope — the
        # origin namespace is only the scope binding's.
        claim_ns = IdempotencyMiddleware._namespace(
            1, "POST:/booking-like", "patient:7"
        )
        fake.store.pop(f"idem:{claim_ns}:{key}:claim", None)

        retry = client.post("/booking-like", headers=headers)
        assert retry.status_code == 200, retry.text
        assert counter["calls"] == 1
    finally:
        restore()


def test_scope_reassert_lost_to_relinked_card_refuses_409(monkeypatch):
    """Round-9 owner P1 (mandatory concurrency test): the successor attempt
    B acquires the claim, but the origin binding was re-bound to another
    card before B's re-assert. Only the attempt bound to the CURRENT card
    may execute: B is refused with 409 idempotency_scope_mismatch, the
    handler never runs."""
    fake = _RelinkedAtReassertRedis()
    counter, restore = _install_patient_worker(monkeypatch, fake)
    from fastapi.testclient import TestClient as TC

    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/booking-like")
    async def _booking_like() -> dict[str, Any]:
        counter["calls"] += 1
        return {"ok": True}

    client = TC(app, raise_server_exceptions=False)
    key = "reassert-409-1"
    headers = {**auth_headers("1"), "Idempotency-Key": key}
    try:
        response = client.post("/booking-like", headers=headers)
        assert response.status_code == 409, response.text
        assert response.json()["code"] == "idempotency_scope_mismatch"
        assert counter["calls"] == 0, (
            "the attempt that lost the binding to a foreign card never executes"
        )
        # The foreign binding survives untouched (compare semantics).
        assert fake.store.get(
            f"idem:{IdempotencyMiddleware._namespace(1, 'POST:/booking-like')}:{key}:pscope",
            "",
        ).startswith("patient:99|")
    finally:
        restore()


def test_local_snapshot_expiry_does_not_slide_on_mirror(monkeypatch):
    """Round-9 owner P2: a scope-only rebind (the Redis→local mirror) keeps
    the entry's ORIGINAL expiry — one replay at hour 23 must not re-arm the
    local snapshot to hour 47 while the Redis binding and response have
    already expired. After the fixed window lapses the local replay is
    GONE; a restore after expiry still gets a fresh window (the eviction-
    restore contract), and a foreign scope never inherits a snapshot."""
    import time as _time

    from fastapi import Response

    try:
        key = "no-slide-1"
        snapshot = (201, {"x": "1"}, b"{}", "application/json", "hash1", "Patient")
        idem_module._local_scope_binding_set("ns1", key, "patient:7", snapshot)
        cache_key = ("ns1", key)
        entry = idem_module._local_scope_bindings[cache_key]

        # The entry was born 23h ago: one hour of its fixed window left.
        aged = (_time.time() + 3600, entry[1], entry[2])
        idem_module._local_scope_bindings[cache_key] = aged

        # A Redis→local mirror at hour 23 (scope-only rebind).
        idem_module._local_scope_binding_mirror("ns1", key, "patient:7")
        mirrored = idem_module._local_scope_bindings[cache_key]
        assert mirrored[2] == snapshot, "the snapshot is preserved (round-8)"
        assert mirrored[0] == aged[0], (
            "the fixed window must NOT slide on a mirror/replay"
        )

        # After the fixed window lapses there is NO local replay left.
        idem_module._local_scope_bindings[cache_key] = (
            _time.time() - 1,
            mirrored[1],
            mirrored[2],
        )
        response, mismatch, role = idem_module._local_patient_outcome_get(
            "ns1", key, "hash1"
        )
        assert response is None, "the expired local outcome is not replayable"

        # An explicit writer (a NEW outcome) still re-arms the window.
        idem_module._local_patient_outcome_store(
            "ns1",
            key,
            "patient:7",
            Response(content=b"{}", status_code=201, media_type="application/json"),
            "hash2",
            "Patient",
        )
        restored = idem_module._local_scope_bindings[cache_key]
        assert restored[0] > _time.time() + 3600 * 23, (
            "a fresh outcome starts a fresh fixed window"
        )

        # A foreign-scope mirror never inherits the entry (or its window).
        idem_module._local_scope_binding_mirror("ns1", "other-key", "patient:8")
        foreign = idem_module._local_scope_bindings[("ns1", "other-key")]
        assert foreign[2] is None
    finally:
        idem_module._local_scope_bindings.clear()
        idem_module._local_scope_bindings_expiry.clear()


def test_legacy_bridge_cutoff_pinned_is_absolute_and_restart_proof(monkeypatch):
    """Round-9 owner P2: the legacy bridge shutdown is an ABSOLUTE,
    deployment-wide cutoff. A pinned past date disables the bridge for
    EVERY worker, and a restart (a fresh process epoch) cannot re-open the
    window; a pinned future date keeps it running regardless of the
    process epoch; max_age = 0 still hard-disables; the UNPINNED fallback
    keeps the transitional process-start semantics."""
    import time as _time

    from app.core.config import settings

    now = _time.time()
    # Pinned in the past + a FRESH process epoch: dead, and a restart
    # (same fresh epoch everywhere) can never re-arm it.
    monkeypatch.setattr(settings, "IDEMPOTENCY_LEGACY_BRIDGE_CUTOFF_EPOCH", now - 1.0)
    monkeypatch.setattr(idem_module, "_LEGACY_BRIDGE_EPOCH", now)
    assert idem_module._legacy_bridge_active() is False
    monkeypatch.setattr(idem_module, "_LEGACY_BRIDGE_EPOCH", now - 10_000.0)
    assert idem_module._legacy_bridge_active() is False

    # Pinned in the future: active on every worker, whatever the fallback
    # epoch says.
    monkeypatch.setattr(
        settings, "IDEMPOTENCY_LEGACY_BRIDGE_CUTOFF_EPOCH", now + 3600.0
    )
    assert idem_module._legacy_bridge_active() is True

    # max_age = 0 hard-disables even a live cutoff.
    monkeypatch.setattr(settings, "IDEMPOTENCY_LEGACY_BRIDGE_MAX_AGE_SECONDS", 0.0)
    assert idem_module._legacy_bridge_active() is False

    # Unpinned: the transitional process-start fallback — reachable ONLY
    # when no shared store answers (no claim AT ALL, anchor cache unset);
    # the process epoch then governs, as documented. get_distributed_claim
    # is stubbed too: on a host with a live Redis service the lazy claim
    # builder would otherwise hand the fallback a REAL store (whose fresh
    # anchor legitimately governs and would mask the fallback semantics).
    saved_claim = idem_module._distributed_claim
    saved_anchor_cache = idem_module._BRIDGE_ANCHOR_CACHE
    idem_module._distributed_claim = None
    monkeypatch.setattr(idem_module, "get_distributed_claim", lambda: None)
    idem_module._BRIDGE_ANCHOR_CACHE = (False, 0.0)
    try:
        monkeypatch.setattr(settings, "IDEMPOTENCY_LEGACY_BRIDGE_CUTOFF_EPOCH", None)
        monkeypatch.setattr(
            settings, "IDEMPOTENCY_LEGACY_BRIDGE_MAX_AGE_SECONDS", 90_090.0
        )
        monkeypatch.setattr(idem_module, "_LEGACY_BRIDGE_EPOCH", now - 100.0)
        assert idem_module._legacy_bridge_active() is True
        monkeypatch.setattr(idem_module, "_LEGACY_BRIDGE_EPOCH", now - 90_100.0)
        assert idem_module._legacy_bridge_active() is False
    finally:
        idem_module._distributed_claim = saved_claim
        idem_module._BRIDGE_ANCHOR_CACHE = saved_anchor_cache


def test_legacy_bridge_anchor_is_shared_across_workers(monkeypatch):
    """Round-9 codex P2 follow-up: the UNPINNED legacy bridge window anchors
    at the DEPLOYMENT's first start, persisted ONCE in the shared store
    (SETNX). Two workers read ONE anchor, a restart (a fresh process with a
    fresh process epoch) can never re-open the window, and once max_age
    from the shared anchor elapses the bridge is dead for every worker."""
    import time as _time

    from app.core.config import settings

    fake = FakeRedis()
    saved_claim = idem_module._distributed_claim
    saved_cache = idem_module._BRIDGE_ANCHOR_CACHE
    saved_epoch = idem_module._LEGACY_BRIDGE_EPOCH
    try:
        monkeypatch.setattr(
            settings, "IDEMPOTENCY_LEGACY_BRIDGE_CUTOFF_EPOCH", None
        )
        t0 = _time.time()

        # Worker 1 anchors the deployment window at its first check.
        monkeypatch.setattr(idem_module, "_distributed_claim", _make_claim(fake))
        monkeypatch.setattr(idem_module, "_BRIDGE_ANCHOR_CACHE", (False, 0.0))
        monkeypatch.setattr(idem_module, "_LEGACY_BRIDGE_EPOCH", t0)
        assert idem_module._legacy_bridge_active() is True
        anchor = fake.store["idem:legacy_bridge_anchor"]
        assert float(anchor) == pytest.approx(t0, abs=5)

        # Worker 2 (another process) reads the SAME anchor — it does not
        # re-arm its own window.
        monkeypatch.setattr(idem_module, "_distributed_claim", _make_claim(fake))
        monkeypatch.setattr(idem_module, "_BRIDGE_ANCHOR_CACHE", (False, 0.0))
        monkeypatch.setattr(idem_module, "_LEGACY_BRIDGE_EPOCH", t0 + 3600)
        assert idem_module._legacy_bridge_active() is True
        assert fake.store["idem:legacy_bridge_anchor"] == anchor, (
            "the anchor is written once per deployment (SETNX)"
        )

        # A RESTART of a worker (fresh process cache, fresh process epoch)
        # cannot re-open the window — the shared anchor still governs.
        monkeypatch.setattr(idem_module, "_BRIDGE_ANCHOR_CACHE", (False, 0.0))
        monkeypatch.setattr(idem_module, "_LEGACY_BRIDGE_EPOCH", t0 + 3600)
        assert idem_module._legacy_bridge_active() is True

        # After max_age measured from the SHARED anchor the bridge is dead
        # for every worker, restarts included.
        fake.store["idem:legacy_bridge_anchor"] = str(t0 - 90_100.0)
        monkeypatch.setattr(idem_module, "_BRIDGE_ANCHOR_CACHE", (False, 0.0))
        assert idem_module._legacy_bridge_active() is False
        monkeypatch.setattr(idem_module, "_BRIDGE_ANCHOR_CACHE", (False, 0.0))
        assert idem_module._legacy_bridge_active() is False
    finally:
        idem_module._distributed_claim = saved_claim
        idem_module._BRIDGE_ANCHOR_CACHE = saved_cache
        idem_module._LEGACY_BRIDGE_EPOCH = saved_epoch
        monkeypatch.undo()

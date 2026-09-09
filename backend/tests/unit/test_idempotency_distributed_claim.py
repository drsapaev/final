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

import uuid
from typing import Any

import pytest
from fastapi import Depends, FastAPI
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

    def eval(self, script: str, numkeys: int, key: str, *args: str) -> int:
        """Emulate the two Lua compare-and-* scripts used by the claim."""
        if self.fail_next_ops > 0:
            self.fail_next_ops -= 1
            raise ConnectionError("simulated transient redis failure")
        if "del" in script:
            if self.store.get(key) == args[0]:
                self.store.pop(key)
                self.ttls.pop(key, None)
                return 1
            return 0
        if "expire" in script:
            if self.store.get(key) == args[0]:
                self.ttls[key] = int(args[1])
                return 1
            return 0
        raise AssertionError(f"unexpected Lua script: {script}")


def auth_headers(sub: str = "1") -> dict[str, str]:
    """Bearer token for a verified principal (Codex R3 #3092 P1)."""
    from app.core.security import create_access_token

    return {"Authorization": f"Bearer {create_access_token(sub)}"}


def nkey(sub: str, key: str, kind: str) -> str:
    """Redis key under the hashed CANONICAL namespace of the given principal
    (Codex R11 #3092: the harness stubs resolve sub "1"/"2" to user 1/2)."""
    ns = IdempotencyMiddleware._namespace(int(sub))
    return f"idem:{ns}:{key}:{kind}"


def _make_claim(fake: FakeRedis) -> DistributedIdempotencyClaim:
    """Build a claim instance without a real Redis (bypass from_url/ping)."""
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._prefix = "idem"
    claim._client = fake
    claim._available = True
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
    idem_module._distributed_claim = _make_claim(fake_redis)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar", False)
    # Codex R11 #3092: the canonical resolution is stubbed — numeric subs are
    # user ids as-is; username subjects get a stable synthetic id (same
    # username -> same namespace within the harness run).
    def _harness_resolve(request, user_id, username, _ids={}):
        if user_id is not None:
            return user_id
        if not username:
            return None
        return _ids.setdefault(username, 9000 + len(_ids) + 1)
    idem_module._resolve_principal_id_sync = _harness_resolve

    counters = {"w1": {"calls": 0, "inline": {"calls": 0, "allowed": True}}, "w2": {"calls": 0, "inline": {"calls": 0, "allowed": True}}}
    client1 = TestClient(_make_app(counters["w1"]), raise_server_exceptions=False)
    client2 = TestClient(_make_app(counters["w2"]), raise_server_exceptions=False)
    yield client1, client2, counters, fake_redis

    idem_module._distributed_claim = saved
    idem_module._check_principal_authorized_sync = saved_auth
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
    assert nkey("1", "crash-key", "claim") not in fake_redis.store, (
        "crashed handler must release the in-flight claim"
    )
    assert nkey("1", "crash-key", "intent") in fake_redis.store, (
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
    assert nkey("1", "bad-key", "intent") not in fake_redis.store, (
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
        idem_module.IdempotencyMiddleware._namespace(1), "lost-key"
    )

    retry = client2.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "lost-key"})
    assert retry.status_code == 409
    assert counters["w2"]["calls"] == 0, "no blind re-execution over an unknown outcome"

    # The outcome lands (e.g. the outcome was actually stored by recovery):
    from fastapi import Response as FastAPIResponse

    claim.store_response(
        idem_module.IdempotencyMiddleware._namespace(1),
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
    monkeypatch.setattr(idem_module, "_resolve_principal_id_sync", lambda *a, **k: None)

    response = client1.post("/echo", headers={**auth_headers("1"), "Idempotency-Key": "ghost-key"})
    assert response.status_code == 403
    assert counters["w1"]["calls"] == 0, "non-executing refusal"

    # Nothing was stored under ANY namespace: after the resolution recovers,
    # the same key executes fresh (no stale replay surface exists).
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

    def _spy(request, user_id, username, jti):
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

    def _checker(request, user_id, username, jti):
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
        idem_module._resolve_principal_id_sync = saved_resolve


def test_optional_redis_down_keeps_in_memory_degrade(monkeypatch):
    """ARQ-fallback (NOT required) claim + outage → original R2 contract:
    traffic degrades to the per-process cache instead of failing."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    saved_resolve = idem_module._resolve_principal_id_sync
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

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

import base64
import json
import uuid
from typing import Any

import pytest
from fastapi import FastAPI
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
    """Redis key under the hashed namespace of the given principal."""
    ns = IdempotencyMiddleware._namespace({"sub": sub})
    return f"idem:{ns}:{key}:{kind}"


def _make_claim(fake: FakeRedis) -> DistributedIdempotencyClaim:
    """Build a claim instance without a real Redis (bypass from_url/ping)."""
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._prefix = "idem"
    claim._client = fake
    claim._available = True
    return claim

def _make_app(counter: dict, call_next_error: Exception | None = None) -> FastAPI:
    app = FastAPI()
    app.add_middleware(IdempotencyMiddleware)

    @app.post("/echo")
    async def _echo() -> dict[str, Any]:
        counter["calls"] += 1
        return {"ok": True, "calls": counter["calls"]}

    @app.post("/boom")
    async def _boom() -> dict[str, str]:
        counter["calls"] += 1
        raise RuntimeError("simulated handler crash")

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
    idem_module._distributed_claim = _make_claim(fake_redis)
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar")

    counters = {"w1": {"calls": 0}, "w2": {"calls": 0}}
    client1 = TestClient(_make_app(counters["w1"]), raise_server_exceptions=False)
    client2 = TestClient(_make_app(counters["w2"]), raise_server_exceptions=False)
    yield client1, client2, counters, fake_redis

    idem_module._distributed_claim = saved
    idem_module._check_principal_authorized_sync = saved_auth


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


def test_handler_crash_releases_claim_so_retry_reruns(two_workers):
    """Non-2xx/crash releases the claim — client can retry with the same key."""
    client1, client2, counters, fake_redis = two_workers

    first = client1.post("/boom", headers={**auth_headers("1"), "Idempotency-Key": "crash-key"})
    assert first.status_code == 500
    assert nkey("1", "crash-key", "claim") not in fake_redis.store, (
        "crashed handler must release the in-flight claim"
    )

    second = client2.post("/boom", headers={**auth_headers("1"), "Idempotency-Key": "crash-key"})
    assert second.status_code == 500
    assert counters["w1"]["calls"] == 1
    assert counters["w2"]["calls"] == 1, (
        "retry after failure must re-execute (errors are not cached)"
    )


def test_redis_unavailable_falls_back_to_in_memory(monkeypatch):
    """Redis down → per-process behavior (original PR-6 contract), no crash."""
    saved = idem_module._distributed_claim
    saved_auth = idem_module._check_principal_authorized_sync
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._client = None
    claim._available = False
    idem_module._distributed_claim = claim
    idem_module._check_principal_authorized_sync = lambda *a, **k: (True, "Registrar")

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
    2xx must not be served to a principal that no longer passes the DB check
    (revoked token / deactivated user) — the request falls through to the
    endpoint instead."""
    client1, client2, counters, _ = two_workers
    key = "revoked-key"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # The DB authorization check now fails for this principal
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (False, None)
    )
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200  # fell through to the endpoint handler
    assert counters["w2"]["calls"] == 1, (
        "unauthorized principal must not receive the cached response"
    )


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
            # user found, active, not blacklisted, role Registrar
            return SimpleNamespace(first=lambda: (7, True, "Registrar", False, False))

    class Override:
        def __init__(self) -> None:
            self.session = SessionSpy()

        def __call__(self):
            yield self.session

    override = Override()
    request = SimpleNamespace(app=SimpleNamespace(dependency_overrides={get_db: override}))
    authorized, role = _check_principal_authorized_sync(request, 7, None, None)
    assert authorized is True
    assert role == "Registrar"
    assert override.session.used, "the override session (endpoint's DB) must be queried"


def test_namespace_is_stable_per_sub_and_hashed():
    """The namespace is a deterministic hash of the verified sub — no raw
    usernames/ids in cache keys, no collisions between principals."""
    from hashlib import sha256

    ns1 = IdempotencyMiddleware._namespace({"sub": "1"})
    ns1_again = IdempotencyMiddleware._namespace({"sub": "1"})
    ns2 = IdempotencyMiddleware._namespace({"sub": "2"})
    assert ns1 == ns1_again
    assert ns1 != ns2
    assert ns1 == sha256(b"1").hexdigest()[:32]


# =====================================================================
# Codex R4 #3092
# =====================================================================


def test_role_change_after_execution_blocks_replay(two_workers, monkeypatch):
    """Codex R4 #3092 (P1): a role change (e.g. registrar demoted to Doctor)
    does not revoke tokens, so the replay must re-check the authorized role.
    A stored response bound to 'Registrar' must not be served when the
    principal's current role differs — the request re-executes under the
    endpoint's require_roles and re-stores with the fresh binding."""
    client1, client2, counters, fake_redis = two_workers
    key = "role-binding-key"
    h1 = auth_headers("1")

    first = client1.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1
    assert counters["w2"]["calls"] == 0

    # The same principal's role changed since execution
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Doctor")
    )
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200  # re-executed under the new role
    assert counters["w2"]["calls"] == 1, (
        "changed-role principal must not receive the cached response"
    )

    # Each further same-role retry replays the response stored under the
    # CURRENT role binding (no endless refusals, no duplicate executions)
    third = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert third.status_code == 200
    assert counters["w2"]["calls"] == 1

    # Role changes again → the Doctor-bound response is refused too
    monkeypatch.setattr(
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (True, "Admin")
    )
    fourth = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert fourth.status_code == 200
    assert counters["w2"]["calls"] == 2


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
        idem_module, "_check_principal_authorized_sync", lambda *a, **k: (False, None)
    )
    second = client2.post("/echo", headers={**h1, "Idempotency-Key": key})
    assert second.status_code == 200  # fell through to the endpoint
    assert counters["w2"]["calls"] == 1, (
        "post-inflight replay must not bypass authorization"
    )

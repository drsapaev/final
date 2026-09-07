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
    see the same distributed claim, while per-process caches stay separate."""
    # Reset the module-level distributed singleton and wire the fake
    saved = idem_module._distributed_claim
    idem_module._distributed_claim = _make_claim(fake_redis)

    counters = {"w1": {"calls": 0}, "w2": {"calls": 0}}
    client1 = TestClient(_make_app(counters["w1"]), raise_server_exceptions=False)
    client2 = TestClient(_make_app(counters["w2"]), raise_server_exceptions=False)
    yield client1, client2, counters, fake_redis

    idem_module._distributed_claim = saved


def test_retry_on_other_worker_replays_response_executes_once(two_workers):
    """Lost response → retry hits ANOTHER worker → replay, handler ran once."""
    client1, client2, counters, _ = two_workers
    headers = {"Idempotency-Key": "codex-r1-lost-response"}

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
    claim_key = "idem:0:overlap-key:claim"
    fake_redis.store[claim_key] = uuid.uuid4().hex

    response = client2.post("/echo", headers={"Idempotency-Key": "overlap-key"})
    assert response.status_code == 409
    assert response.headers.get("Retry-After") == "1"
    assert counters["w2"]["calls"] == 0, (
        "overlapping retry must not execute the handler a second time"
    )


def test_in_flight_claim_replays_if_response_landed_between_attempts(two_workers):
    """Claim fails but response completes before the re-check → replay, 200."""
    client1, client2, counters, fake_redis = two_workers

    key = "race-key"
    # Worker 1 completes: snapshot stored, claim released
    first = client1.post("/echo", headers={"Idempotency-Key": key})
    assert first.status_code == 200
    # (worker 2's per-process cache is cold; only Redis knows the response)
    resp_snapshot_key = "idem:0:race-key:resp"
    assert resp_snapshot_key in fake_redis.store

    # A claim is (re)acquired concurrently — then worker 2 retries:
    # acquire fails on the stale claim, but the re-check finds the snapshot.
    fake_redis.store["idem:0:race-key:claim"] = uuid.uuid4().hex
    second = client2.post("/echo", headers={"Idempotency-Key": key})
    assert second.status_code == 200
    assert counters["w2"]["calls"] == 0


def test_handler_crash_releases_claim_so_retry_reruns(two_workers):
    """Non-2xx/crash releases the claim — client can retry with the same key."""
    client1, client2, counters, fake_redis = two_workers

    first = client1.post("/boom", headers={"Idempotency-Key": "crash-key"})
    assert first.status_code == 500
    assert "idem:0:crash-key:claim" not in fake_redis.store, (
        "crashed handler must release the in-flight claim"
    )

    second = client2.post("/boom", headers={"Idempotency-Key": "crash-key"})
    assert second.status_code == 500
    assert counters["w1"]["calls"] == 1
    assert counters["w2"]["calls"] == 1, (
        "retry after failure must re-execute (errors are not cached)"
    )


def test_redis_unavailable_falls_back_to_in_memory(monkeypatch):
    """Redis down → per-process behavior (original PR-6 contract), no crash."""
    saved = idem_module._distributed_claim
    claim = object.__new__(DistributedIdempotencyClaim)
    claim._ttl = 24 * 60 * 60
    claim._client = None
    claim._available = False
    idem_module._distributed_claim = claim

    try:
        counter = {"calls": 0}
        app = _make_app(counter)
        client = TestClient(app, raise_server_exceptions=False)

        r1 = client.post("/echo", headers={"Idempotency-Key": "mem-key"})
        assert r1.status_code == 200
        r2 = client.post("/echo", headers={"Idempotency-Key": "mem-key"})
        assert r2.status_code == 200
        assert counter["calls"] == 1, "in-memory dedup still works in fallback"
    finally:
        idem_module._distributed_claim = saved


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
    claim.store_response(7, "k", original, payload_hash="deadbeef")
    replayed, stored_hash = claim.load_response(7, "k")
    assert replayed is not None
    assert replayed.status_code == 200
    assert replayed.body == b'{"invoice_id": 42}'
    assert replayed.headers.get("x-custom") == "abc"
    assert stored_hash == "deadbeef"


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

    first = client1.post("/echo", json={"doctor": 1}, headers={"Idempotency-Key": key})
    assert first.status_code == 200
    assert counters["w1"]["calls"] == 1

    # Registrar changed the cart before retrying — same key, different body
    changed = client2.post("/echo", json={"doctor": 2}, headers={"Idempotency-Key": key})
    assert changed.status_code == 409
    assert "different request payload" in changed.text
    # The changed retry must NOT execute the handler either
    assert counters["w2"]["calls"] == 0

    # Unchanged retry (lost-response replay scenario) still replays the
    # original 200 with the original body.
    same = client2.post("/echo", json={"doctor": 1}, headers={"Idempotency-Key": key})
    assert same.status_code == 200
    assert same.json()["ok"] is True
    assert counters["w2"]["calls"] == 0


def test_changed_payload_local_cache_mismatch_returns_409(two_workers):
    """Local (same-worker) path: cached response + different body → 409."""
    client1, client2, counters, _ = two_workers
    key = "codex-r2-local-mismatch"

    first = client1.post("/echo", json={"v": 1}, headers={"Idempotency-Key": key})
    assert first.status_code == 200
    second = client1.post("/echo", json={"v": 999}, headers={"Idempotency-Key": key})
    assert second.status_code == 409
    assert counters["w1"]["calls"] == 1, "changed payload must not execute the handler"


def test_in_flight_lease_is_short_not_24h(fake_redis):
    """Codex R2 #3092 (P2): the claim lives lease_seconds (90s), not the
    response TTL — a dead worker 409-locks its key for seconds, not a day."""
    claim = _make_claim(fake_redis)
    assert claim.acquire(1, "lease-key") is True
    claim_ttl = fake_redis.ttls["idem:1:lease-key:claim"]
    assert claim_ttl == claim.lease_seconds
    assert claim_ttl < 24 * 60 * 60
    assert claim_ttl == 90


def test_lease_renewal_extends_only_existing_claim(fake_redis):
    """renew() extends a live claim (XX) and never resurrects a lapsed one."""
    claim = _make_claim(fake_redis)
    assert claim.acquire(1, "renew-key") is True
    assert fake_redis.store["idem:1:renew-key:claim"]
    assert claim.renew(1, "renew-key") is True
    assert fake_redis.ttls["idem:1:renew-key:claim"] == 90

    # Lapsed claim (worker died, TTL elapsed) — renewal must NOT resurrect it
    fake_redis.store.pop("idem:1:renew-key:claim")
    assert claim.renew(1, "renew-key") is False
    assert "idem:1:renew-key:claim" not in fake_redis.store


def test_transient_redis_failure_recovers(monkeypatch, fake_redis):
    """Codex R2 #3092 (P1): a Redis timeout/restart degrades the layer, then
    coordination RESUMES after the cooldown — the worker is not permanently
    disabled until restart."""
    monkeypatch.setattr(idem_module, "_RECONNECT_COOLDOWN_SECONDS", 0.0)
    claim = _make_claim(fake_redis)

    # Simulate a transient failure: the next op raises
    fake_redis.fail_next_ops = 1
    assert claim.acquire(1, "recover-key") is False  # op failed → degrade
    assert claim.available is False

    # Cooldown elapsed (0s): the next acquire re-probes and succeeds
    assert claim.acquire(1, "recover-key") is True
    assert claim.available is True
    assert "idem:1:recover-key:claim" in fake_redis.store


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

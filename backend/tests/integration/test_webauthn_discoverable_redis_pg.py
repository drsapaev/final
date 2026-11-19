"""Distributed WebAuthn quota and one-use tests against real Redis."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
import redis

from app.core.config import settings
from app.services import webauthn_service as ws

pytestmark = pytest.mark.integration


@pytest.fixture
def shared_redis(monkeypatch):
    url = os.environ.get("WEBAUTHN_TEST_REDIS_URL") or os.environ.get("ARQ_REDIS_URL")
    if not url:
        if os.environ.get("CI") == "true":
            pytest.fail("CI Redis is required")
        pytest.skip("provide disposable Redis")
    client = redis.Redis.from_url(
        url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2
    )
    client.ping()
    prefix = f"test:{{discoverable}}:{uuid4().hex}:"
    monkeypatch.setattr(ws, "_DISCOVERABLE_PREFIX", prefix)
    monkeypatch.setattr(settings, "TESTING", False)
    monkeypatch.setenv("REDIS_URL", url)
    monkeypatch.setattr(ws, "_DISCOVERABLE_GLOBAL_LIMIT", 4)
    monkeypatch.setattr(ws, "_DISCOVERABLE_CLIENT_LIMIT", 2)
    monkeypatch.setattr(ws, "_DISCOVERABLE_GLOBAL_RATE", 100)
    monkeypatch.setattr(ws, "_DISCOVERABLE_CLIENT_RATE", 100)
    yield client, prefix
    keys = list(client.scan_iter(prefix + "*"))
    if keys:
        client.delete(*keys)
    client.close()


def test_distributed_capacity_and_getdel_race(shared_redis):
    client, prefix = shared_redis

    def begin(index):
        ceremony = ws.secrets.token_urlsafe(32)
        try:
            ws._store_discoverable_ceremony(
                ceremony, f"test-client-{index}", b"binary\xff"
            )
            return ceremony
        except ws.WebAuthnQuotaExceeded:
            return None

    with ThreadPoolExecutor(max_workers=16) as executor:
        ceremonies = list(executor.map(begin, range(16)))
    accepted = [item for item in ceremonies if item]
    assert len(accepted) == 4
    assert client.zcard(prefix + "discoverable:outstanding") == 4
    assert 0 < client.ttl(prefix + "discoverable:outstanding") <= 300
    ceremony = accepted[0]

    def finish(_):
        try:
            return ws._consume_discoverable_ceremony(ceremony, "test-client-finish")
        except ValueError:
            return None

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(finish, range(8)))
    assert results.count(b"binary\xff") == 1
    assert results.count(None) == 7
    assert client.zcard(prefix + "discoverable:outstanding") == 3
    assert not client.exists(prefix + "discoverable:" + ceremony)
    ws._store_discoverable_ceremony(
        ws.secrets.token_urlsafe(32), "test-new", b"challenge"
    )


def test_client_and_legacy_quotas_are_bounded_and_isolated(shared_redis):
    client, prefix = shared_redis
    for _ in range(2):
        ws._store_discoverable_ceremony(
            ws.secrets.token_urlsafe(32), "same-client", b"challenge"
        )
    with pytest.raises(ws.WebAuthnQuotaExceeded):
        ws._store_discoverable_ceremony(
            ws.secrets.token_urlsafe(32), "same-client", b"challenge"
        )
    for index in range(4):
        ws._store_ceremony(
            client,
            ws.secrets.token_urlsafe(32),
            index + 1,
            b"challenge",
            f"legacy-{index}",
        )
    assert client.zcard(prefix + "login:outstanding") == 4
    with pytest.raises(ws.WebAuthnQuotaExceeded):
        ws._store_ceremony(
            client, ws.secrets.token_urlsafe(32), 99, b"challenge", "legacy-other"
        )
    # A saturated legacy plane does not reveal IDs via discoverable capacity.
    ws._store_discoverable_ceremony(
        ws.secrets.token_urlsafe(32), "another-client", b"challenge"
    )
    assert client.zcard(prefix + "discoverable:outstanding") == 3


def test_inflight_old_legacy_key_is_consumed_once(shared_redis):
    client, _ = shared_redis
    ceremony = ws.secrets.token_urlsafe(32)
    old_key = f"webauthn:login:{ceremony}"
    try:
        client.set(old_key, '{"patient_id":17,"challenge":"YmluYXJ5"}', ex=300)
        assert ws._consume_ceremony(ceremony, 17) == b"binary"
        with pytest.raises(ValueError):
            ws._consume_ceremony(ceremony, 17)
    finally:
        client.delete(old_key)


@pytest.mark.parametrize("patient_id", [1234, 987654321])
def test_legacy_and_discoverable_saturation_are_independent(
    shared_redis, monkeypatch, patient_id, db_session
):
    client, prefix = shared_redis
    monkeypatch.setattr(settings, "FRONTEND_URL", "https://clinic.example")
    monkeypatch.setattr(ws, "_DISCOVERABLE_GLOBAL_LIMIT", 1)
    legacy = ws.begin_passkey_authentication(
        db_session, patient_id, client_ip="legacy-client"
    )
    assert client.zcard(prefix + "login:outstanding") == 1
    discovery = ws.begin_discoverable_authentication("discovery-client")
    assert client.zcard(prefix + "discoverable:outstanding") == 1
    saturated_legacy = ws.begin_passkey_authentication(
        db_session, patient_id + 1, client_ip="legacy-other"
    )
    assert set(legacy) == set(saturated_legacy)
    assert not client.exists(prefix + "login:" + saturated_legacy["ceremony_id"])
    with pytest.raises(ws.WebAuthnQuotaExceeded):
        ws.begin_discoverable_authentication("discovery-other")
    ws._consume_ceremony(legacy["ceremony_id"], patient_id, "legacy-client")
    # Discovery remains saturated after legacy is freed, and the converse too.
    with pytest.raises(ws.WebAuthnQuotaExceeded):
        ws.begin_discoverable_authentication("discovery-other")
    ws.begin_passkey_authentication(db_session, patient_id, client_ip="legacy-client")
    assert client.zcard(prefix + "login:outstanding") == 1
    assert ws._consume_discoverable_ceremony(
        discovery["ceremony_id"], "discovery-client"
    )

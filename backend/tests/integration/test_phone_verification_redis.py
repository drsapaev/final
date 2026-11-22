"""Two-service Redis races for phone verification; no external SMS is sent."""

import asyncio
import json
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from urllib.parse import urlsplit

import pytest
import redis

from app.services.phone_verification_service import PhoneVerificationService
from app.services.phone_verification_store import PhoneStoreUnavailable, RedisPhoneStore
from app.services.sms_providers import SMSResponse


@pytest.fixture
def services():
    url = os.getenv("PHONE_VERIFICATION_REDIS_TEST_URL")
    if not url and os.getenv("CI") == "true" and os.getenv("GITHUB_ACTIONS") == "true":
        candidate = os.getenv("REDIS_URL") or os.getenv("ARQ_REDIS_URL")
        if candidate:
            parsed = urlsplit(candidate)
            if parsed.scheme == "redis" and parsed.hostname in {"localhost", "127.0.0.1", "::1"}:
                url = candidate
    if not url:
        pytest.skip("PHONE_VERIFICATION_REDIS_TEST_URL is required")
    client = redis.Redis.from_url(url, decode_responses=True, socket_connect_timeout=2, socket_timeout=2)
    client.ping()
    phone = "+998" + "".join(str(secrets.randbelow(10)) for _ in range(9))
    items = [PhoneVerificationService(RedisPhoneStore(client)) for _ in range(2)]
    for item in items:
        item.generate_verification_code = lambda: "123456"

        async def send_sms(**_kwargs):
            return SMSResponse(success=True, provider="synthetic")

        item.sms_manager = SimpleNamespace(send_sms=send_sms)
    yield items, client, phone
    key = items[0]._get_code_key(phone, "verification")
    client.delete(*RedisPhoneStore._keys(key))


def identity():
    return {"actor_id": 17, "actor_epoch": 5, "actor_jti": "synthetic-session"}


@pytest.mark.asyncio
async def test_cross_worker_single_use_and_owner_isolation(services):
    (first, second), client, phone = services
    assert (await first.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))["success"]
    key = first._get_code_key(phone, "verification")
    raw = client.get(RedisPhoneStore._keys(key)[0])
    assert phone not in key and phone not in raw and "123456" not in raw
    assert second.verify_code(phone, "123456", actor_id=18, actor_epoch=5, actor_jti="other", allow_admin=True)["error_code"] == "CODE_NOT_FOUND"
    barrier = threading.Barrier(2)

    def consume(service):
        barrier.wait(timeout=5)
        return service.verify_code(phone, "123456", **identity())

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(consume, item) for item in (first, second)]
        results = [future.result(timeout=5) for future in futures]
    assert sum(result["success"] for result in results) == 1


@pytest.mark.asyncio
async def test_reset_deadline_uses_atomic_ttl_across_skewed_workers(services, monkeypatch):
    (sender, verifier), client, phone = services
    import app.services.phone_verification_service as service_module

    key = sender._get_code_key(phone, "password_reset")
    record_key = RedisPhoneStore._keys(key)[0]
    try:
        monkeypatch.setattr(service_module.time, "time", lambda: 2_000_000_000.0)
        assert (await sender.send_verification_code(phone, purpose="password_reset", account_binding=(42, 8)))["success"]
        assert client.pexpire(record_key, 10000)
        monkeypatch.setattr(service_module.time, "time", lambda: 1_000_000_000.0)
        real_verify = verifier._store.verify

        def delayed_verify(*args):
            time.sleep(0.2)
            return real_verify(*args)

        monkeypatch.setattr(verifier._store, "verify", delayed_verify)
        before = time.monotonic()
        result = verifier.verify_code(phone, "123456", purpose="password_reset", include_account_binding=True)
        after = time.monotonic()
        assert result["success"] and result["account_binding"] == (42, 8)
        assert result["expires_at"] > 2_000_000_000.0
        assert after < result["expires_monotonic"] <= before + 10
        # Delay before executing Lua cannot extend the local deadline.
        assert result["expires_monotonic"] <= after + 9.9
        assert verifier.verify_code(phone, "123456", purpose="password_reset", include_account_binding=True)["error_code"] == "CODE_NOT_FOUND"
    finally:
        client.delete(*RedisPhoneStore._keys(key))


@pytest.mark.asyncio
async def test_cross_worker_reservation_and_failed_delivery_keep_cooldown(services):
    (first, second), _client, phone = services
    entered = asyncio.Event()
    unblock = asyncio.Event()

    async def blocked_send(**_kwargs):
        entered.set()
        await unblock.wait()
        return SMSResponse(success=False, error="synthetic")

    first.sms_manager.send_sms = blocked_send
    pending = asyncio.create_task(first.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))
    await entered.wait()
    assert (await second.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))["error_code"] == "RATE_LIMITED"
    unblock.set()
    assert (await pending)["error_code"] == "SMS_SEND_FAILED"
    assert (await second.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))["error_code"] == "RATE_LIMITED"
    assert second.verify_code(phone, "123456", **identity())["error_code"] == "CODE_NOT_FOUND"


@pytest.mark.asyncio
async def test_cross_worker_attempts_cannot_be_reset_or_bypassed(services):
    (first, second), _client, phone = services
    assert (await first.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))["success"]
    barrier = threading.Barrier(3)

    def wrong(service):
        barrier.wait(timeout=5)
        return service.verify_code(phone, "999999", **identity())

    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(wrong, item) for item in (first, second, first)]
        results = [future.result(timeout=5) for future in futures]
    assert sorted(result["attempts_left"] for result in results) == [0, 1, 2]
    assert second.verify_code(phone, "123456", **identity())["error_code"] == "MAX_ATTEMPTS_EXCEEDED"


@pytest.mark.asyncio
async def test_failure_budget_survives_reissue_across_workers(services):
    (first, second), client, phone = services
    key = first._get_code_key(phone, "verification")
    for index in range(4):
        if index:
            # Simulate expiry of the independent resend cooldown.
            client.delete(RedisPhoneStore._keys(key)[2])
        sender = first if index % 2 == 0 else second
        assert (await sender.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))["success"]
        for _ in range(3 if index < 3 else 1):
            assert sender.verify_code(phone, "999999", **identity())["error_code"] == "INVALID_CODE"
    assert second.verify_code(phone, "123456", **identity())["error_code"] == "MAX_ATTEMPTS_EXCEEDED"
    assert int(client.get(RedisPhoneStore._keys(key)[3])) == 10
    assert 0 < client.ttl(RedisPhoneStore._keys(key)[3]) <= 3600


@pytest.mark.asyncio
async def test_late_sender_cannot_replace_new_reservation(services):
    (first, second), client, phone = services
    key = first._get_code_key(phone, "verification")
    first_store, second_store = first._store, second._store
    assert first_store.reserve(key, "synthetic-old", 90, 60)
    # Simulate expiration on this dedicated, disposable Redis instance.
    client.delete(*RedisPhoneStore._keys(key)[1:])
    assert second_store.reserve(key, "synthetic-new", 90, 60)
    assert not first_store.publish(key, "synthetic-old", "{}", 60, 60)
    assert client.get(RedisPhoneStore._keys(key)[1]) == "synthetic-new"


def test_publish_ttl_is_bounded_by_redis_reservation_age(services):
    (first, _second), client, phone = services
    key = first._get_code_key(phone, "verification")
    record_key, lease_key, _cooldown, _failures = RedisPhoneStore._keys(key)
    assert first._store.reserve(key, "synthetic-lease", 90, 60)
    # Simulate 80 seconds spent before the delayed publish arrives at Redis.
    assert client.pexpire(lease_key, 10000)
    assert first._store.publish(key, "synthetic-lease", "{}", 300, 60, 300, 90)
    assert 0 < client.pttl(record_key) <= 220000

    client.delete(*RedisPhoneStore._keys(key))
    assert first._store.reserve(key, "synthetic-expired", 90, 60)
    assert client.pexpire(lease_key, 84000)
    assert not first._store.publish(key, "synthetic-expired", "{}", 5, 60, 5, 90)
    assert client.get(record_key) is None


@pytest.mark.asyncio
async def test_nonce_recheck_prevents_old_lookup_from_using_new_record(services):
    (first, second), client, phone = services
    assert (await first.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))["success"]
    key = first._get_code_key(phone, "verification")
    actor = ("17", "5", "synthetic-session")
    old = first._store.status(key, actor, False)
    old_digest = first._code_digest(key, old["nonce"], "123456")
    # Simulate the expiry of cooldown on this isolated test Redis.
    client.delete(RedisPhoneStore._keys(key)[2])
    assert (await second.send_verification_code(phone, owner_binding=(17, 5, "synthetic-session")))["success"]
    assert first._store.verify(key, old["nonce"], old_digest, actor, False, False, True, 3)[0] == "missing"
    assert second.verify_code(phone, "123456", **identity())["success"]


def test_runtime_outage_is_typed_and_fails_closed(services):
    (first, _second), _client, phone = services

    class Broken:
        def eval(self, *_args):
            raise redis.ConnectionError("synthetic")

    first._store = RedisPhoneStore(Broken())
    with pytest.raises(PhoneStoreUnavailable):
        first.verify_code(phone, "123456", **identity())
    with pytest.raises(PhoneStoreUnavailable):
        first.get_verification_status(phone, **identity())
    with pytest.raises(PhoneStoreUnavailable):
        first.cancel_verification(phone, **identity())
    with pytest.raises(PhoneStoreUnavailable):
        first.consume_ip_verify_budget("198.51.100.1")


def test_ip_budget_is_shared_atomic_bounded_and_private(services):
    (first, second), client, _phone = services
    ip = f"2001:db8::{secrets.randbelow(65536):x}"
    key = "phonever:reset-ip:" + first._mac(
        json.dumps(["phone-reset-verify-ip-v1", ip], separators=(",", ":"))
    )
    try:
        with ThreadPoolExecutor(max_workers=12) as pool:
            results = list(pool.map(lambda index: (first if index % 2 else second).consume_ip_verify_budget(ip), range(60)))
        assert sum(results) == 30
        assert int(client.get(key)) == 30
        assert ip not in key and 0 < client.ttl(key) <= 60
        client.set(key, "broken", ex=60)
        with pytest.raises(PhoneStoreUnavailable):
            first.consume_ip_verify_budget(ip)
        client.set(key, "1")
        with pytest.raises(PhoneStoreUnavailable):
            first.consume_ip_verify_budget(ip)
    finally:
        client.delete(key)


def test_corrupted_or_unbound_records_fail_closed(services):
    (first, second), client, phone = services
    key = first._get_code_key(phone, "verification")
    record_key = RedisPhoneStore._keys(key)[0]
    client.set(record_key, "not-json", ex=60)
    assert first.verify_code(phone, "123456", **identity())["error_code"] == "CODE_NOT_FOUND"
    assert client.get(record_key) is None
    client.set(record_key, '{"version":true,"owner":null}', ex=60)
    assert second.verify_code(phone, "123456", **identity(), allow_admin=True)["error_code"] == "CODE_NOT_FOUND"
    assert client.get(record_key) is None

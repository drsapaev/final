"""Security and delivery contracts for the verification service."""

import asyncio
import secrets
import threading
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.services.phone_verification_service import PhoneVerificationService
from app.services.phone_verification_store import (
    MemoryPhoneStore,
    PhoneStoreUnavailable,
)
from app.services.sms_providers import SMSManager, SMSProviderType, SMSResponse


@pytest.fixture
def phone():
    return "+998" + "".join(str(secrets.randbelow(10)) for _ in range(9))


@pytest.fixture
def service():
    instance = PhoneVerificationService(MemoryPhoneStore())
    instance.generate_verification_code = lambda: "123456"

    async def send_sms(**_kwargs):
        return SMSResponse(success=True, provider="synthetic")

    instance.sms_manager = SimpleNamespace(send_sms=send_sms)
    return instance


def actor(user=7, epoch=2, jti="synthetic-jti"):
    return {"actor_id": user, "actor_epoch": epoch, "actor_jti": jti}


@pytest.mark.asyncio
async def test_owner_epoch_jti_and_unbound_records_are_not_disclosed(service, phone):
    assert (await service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti")))["success"]
    for other in (actor(8), actor(epoch=3), actor(jti="other")):
        assert service.get_verification_status(phone, **other) == {"exists": False, "verified": False}
        assert not service.cancel_verification(phone, **other)
        assert service.verify_code(phone, "123456", **other)["error_code"] == "CODE_NOT_FOUND"
    assert service.get_verification_status(phone, **actor(), allow_admin=True)["exists"]
    assert service.verify_code(phone, "123456", **actor())["success"]
    assert service.verify_code(phone, "123456", **actor())["error_code"] == "CODE_NOT_FOUND"

    phone2 = phone + "0"
    assert (await service.send_verification_code(phone2))["success"]
    assert service.get_verification_status(phone2, **actor()) == {"exists": False, "verified": False}
    assert service.verify_code(phone2, "123456", **actor())["error_code"] == "CODE_NOT_FOUND"
    assert service.verify_code(phone2, "123456", **actor(), allow_admin=True)["success"]


@pytest.mark.asyncio
async def test_admin_cannot_consume_another_sessions_bound_code(service, phone):
    assert (await service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti")))["success"]
    assert service.verify_code(phone, "123456", **actor(user=9), allow_admin=True)["error_code"] == "CODE_NOT_FOUND"
    assert not service.cancel_verification(phone, **actor(user=9), allow_admin=True)
    assert service.verify_code(phone, "123456", **actor())["success"]


@pytest.mark.asyncio
async def test_attempt_limit_and_success_are_atomic(service, phone):
    assert (await service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti")))["success"]
    for expected in (2, 1, 0):
        assert service.verify_code(phone, "999999", **actor())["attempts_left"] == expected
    assert service.verify_code(phone, "123456", **actor())["error_code"] == "MAX_ATTEMPTS_EXCEEDED"

    phone2 = phone + "0"
    assert (await service.send_verification_code(phone2, owner_binding=(7, 2, "synthetic-jti")))["success"]
    barrier = threading.Barrier(2)

    def verify():
        barrier.wait(timeout=5)
        return service.verify_code(phone2, "123456", **actor())

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result(timeout=5) for f in (pool.submit(verify), pool.submit(verify))]
    assert sum(result["success"] for result in results) == 1


@pytest.mark.asyncio
async def test_concurrent_sends_reserve_before_provider(service, phone):
    entered = asyncio.Event()
    proceed = asyncio.Event()
    calls = []

    async def slow_send(**_kwargs):
        calls.append(1)
        entered.set()
        await proceed.wait()
        return SMSResponse(success=True, provider="synthetic")

    service.sms_manager.send_sms = slow_send
    first = asyncio.create_task(service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti")))
    await entered.wait()
    second = await service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti"))
    assert second["error_code"] == "RATE_LIMITED" and len(calls) == 1
    proceed.set()
    assert (await first)["success"]


@pytest.mark.asyncio
@pytest.mark.parametrize("message", ["", "synthetic custom message without placeholder"])
async def test_custom_message_without_placeholder_does_not_reserve_or_send(service, phone, message, monkeypatch, caplog):
    def unexpected_reserve(*_args):
        pytest.fail("invalid message must not reserve")

    async def unexpected_send(**_kwargs):
        pytest.fail("invalid message must not send")

    monkeypatch.setattr(service._store, "reserve", unexpected_reserve)
    service.sms_manager.send_sms = unexpected_send
    result = await service.send_verification_code(phone, custom_message=message, owner_binding=(7, 2, "synthetic-jti"))
    assert result["error_code"] == "INVALID_CUSTOM_MESSAGE"
    if message:
        assert message not in caplog.text and message not in str(result)


@pytest.mark.asyncio
async def test_custom_message_placeholder_is_replaced_and_code_is_usable(service, phone):
    messages = []

    async def capture_send(**kwargs):
        messages.append(kwargs["text"])
        return SMSResponse(success=True, provider="synthetic")

    service.sms_manager.send_sms = capture_send
    result = await service.send_verification_code(
        phone, custom_message="Your code: {code}", owner_binding=(7, 2, "synthetic-jti")
    )
    assert result["success"]
    assert messages == ["Your code: 123456"]
    assert service.verify_code(phone, "123456", **actor())["success"]


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", ["provider", "cancel", "expired"])
async def test_failed_or_cancelled_send_keeps_cooldown_and_no_valid_code(service, phone, failure):
    entered = asyncio.Event()
    blocker = asyncio.Event()

    async def failing_send(**_kwargs):
        entered.set()
        if failure == "cancel":
            await blocker.wait()
        return SMSResponse(success=failure == "expired", provider="synthetic")

    service.sms_manager.send_sms = failing_send
    if failure == "expired":
        service.code_ttl_minutes = 0
    task = asyncio.create_task(service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti")))
    await entered.wait()
    if failure == "cancel":
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    elif failure == "expired":
        with pytest.raises(PhoneStoreUnavailable):
            await task
    else:
        assert (await task)["error_code"] == "SMS_SEND_FAILED"
    assert (await service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti")))["error_code"] == "RATE_LIMITED"
    assert service.verify_code(phone, "123456", **actor())["error_code"] == "CODE_NOT_FOUND"


def test_concurrent_first_use_shares_one_store(monkeypatch):
    monkeypatch.setenv("TESTING", "1")
    service = PhoneVerificationService()
    barrier = threading.Barrier(8)

    def get_store():
        barrier.wait(timeout=5)
        return service._get_store()

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(get_store) for _ in range(8)]
        stores = [future.result(timeout=5) for future in futures]
    assert len({id(store) for store in stores}) == 1


def test_memory_ip_budget_isolated_and_bounded(service):
    assert all(service.consume_ip_verify_budget("198.51.100.1") for _ in range(30))
    assert not service.consume_ip_verify_budget("198.51.100.1")
    assert service.consume_ip_verify_budget("198.51.100.2")
    with pytest.raises(PhoneStoreUnavailable):
        service.consume_ip_verify_budget("")


def test_memory_publish_ttl_is_bounded_by_reservation_age(service):
    import time

    store = service._store
    key = "synthetic-key"
    assert store.reserve(key, "synthetic-lease", 90, 60)
    store._leases[key] = ("synthetic-lease", time.monotonic() + 10)
    assert store.publish(key, "synthetic-lease", "{}", 300, 60, 300, 90)
    assert 0 < store._records[key][1] - time.monotonic() <= 220

    assert store.reserve("expired-key", "synthetic-expired", 90, 60)
    store._leases["expired-key"] = ("synthetic-expired", time.monotonic() + 84)
    assert not store.publish("expired-key", "synthetic-expired", "{}", 5, 60, 5, 90)


@pytest.mark.asyncio
@pytest.mark.parametrize("raises", [False, True])
async def test_provider_error_and_log_never_expose_phone_or_code(service, phone, caplog, raises):
    async def failing_send(**_kwargs):
        if raises:
            raise RuntimeError(f"synthetic leak {phone} 123456")
        return SMSResponse(success=False, error=f"synthetic leak {phone} 123456")

    service.sms_manager.send_sms = failing_send
    response = await service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti"))
    assert phone not in str(response) and "123456" not in str(response)
    assert phone not in caplog.text and "123456" not in caplog.text


@pytest.mark.asyncio
async def test_real_sms_manager_contract_uses_text_not_message(service, phone):
    class Provider:
        async def send_sms(self, message):
            assert message.phone == phone
            assert "123456" in message.text
            return SMSResponse(success=True, provider="synthetic")

    manager = SMSManager()
    manager.providers = {SMSProviderType.MOCK: Provider()}
    manager.default_provider = SMSProviderType.MOCK
    service.sms_manager = manager
    assert (await service.send_verification_code(phone, owner_binding=(7, 2, "synthetic-jti")))["success"]


@pytest.mark.asyncio
@pytest.mark.parametrize("explicit", [False, True])
async def test_mock_sms_is_unavailable_outside_testing(monkeypatch, phone, explicit):
    from app.core.config import settings

    monkeypatch.setenv("TESTING", "0")
    monkeypatch.setattr(settings, "ENV", "production")
    service = PhoneVerificationService(MemoryPhoneStore())
    manager = SMSManager()
    manager.default_provider = SMSProviderType.MOCK
    service.sms_manager = manager
    with pytest.raises(PhoneStoreUnavailable):
        await service.send_verification_code(
            phone, provider_type=SMSProviderType.MOCK if explicit else None,
            owner_binding=(7, 2, "synthetic-jti"),
        )


@pytest.mark.asyncio
async def test_password_reset_binding_is_tuple_and_never_exposed_to_self_service(service, phone):
    assert (await service.send_verification_code(phone, purpose="password_reset", account_binding=(42, 8)))["success"]
    key = service._get_code_key(phone, "password_reset")
    expiry = service._store.status(key, None, False, True)["expires_at"]
    assert service.verify_code(phone, "123456", purpose="password_reset", **actor(), allow_admin=True)["error_code"] == "CODE_NOT_FOUND"
    result = service.verify_code(phone, "123456", purpose="password_reset", include_account_binding=True)
    assert result["success"] and result["account_binding"] == (42, 8)
    assert isinstance(result["expires_at"], float) and result["expires_at"] == expiry


@pytest.mark.asyncio
@pytest.mark.parametrize("bad_expiry", [None, True, 0, -1, "123", float("nan"), float("inf")])
async def test_password_reset_rejects_invalid_consumed_expiry(service, phone, bad_expiry):
    import json

    assert (await service.send_verification_code(phone, purpose="password_reset", account_binding=(42, 8)))["success"]
    key = service._get_code_key(phone, "password_reset")
    payload, ttl = service._store._records[key]
    record = json.loads(payload)
    record["expires_at"] = bad_expiry
    service._store._records[key] = (json.dumps(record), ttl)
    assert service.verify_code(phone, "123456", purpose="password_reset", include_account_binding=True)["error_code"] == "CODE_NOT_FOUND"
    assert service._store.status(key, None, False, True) is None


def test_storage_failures_are_not_misreported_as_missing(service, phone):
    class Down:
        def status(self, *_args):
            raise PhoneStoreUnavailable("synthetic")

        def cancel(self, *_args):
            raise PhoneStoreUnavailable("synthetic")

        def statistics(self):
            raise PhoneStoreUnavailable("synthetic")

    service._store = Down()
    for operation in (
        lambda: service.get_verification_status(phone, **actor()),
        lambda: service.cancel_verification(phone, **actor()),
        lambda: service.verify_code(phone, "123456", **actor()),
        service.get_statistics,
    ):
        with pytest.raises(PhoneStoreUnavailable):
            operation()


def test_malformed_owner_is_never_interpreted_as_unbound(service, phone):
    import json
    import time

    key = service._get_code_key(phone, "verification")
    service._store._records[key] = (json.dumps({"version": 1}), time.monotonic() + 60)
    assert service.get_verification_status(phone, **actor(), allow_admin=True) == {"exists": False, "verified": False}


def test_no_memory_fallback_outside_test_mode(monkeypatch):
    from app.core.config import settings
    from app.services import phone_verification_service as module

    class UnavailableRedis:
        def __init__(self):
            raise OSError("synthetic")

    monkeypatch.setattr(module, "RedisPhoneStore", UnavailableRedis)
    monkeypatch.setenv("TESTING", "0")
    with pytest.raises(PhoneStoreUnavailable):
        PhoneVerificationService()._get_store()
    monkeypatch.setenv("TESTING", "1")
    monkeypatch.setattr(settings, "ENV", "production")
    with pytest.raises(PhoneStoreUnavailable):
        PhoneVerificationService()._get_store()

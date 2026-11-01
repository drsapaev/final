"""Phase 0 PR-A1 — patient OTP foundation (unit).

Covers owner-approved identity contract v3:
- canonical +998 normalization;
- Redis-semantics OTP in TESTING in-memory fallback (hash-only storage,
  cooldown, hourly cap, single-use grant);
- anti-enum uniformity (all verify failures share one generic detail);
- login resolver is FAIL-CLOSED on ambiguous phone: exactly-one candidate
  or generic failure — never .first() (UserProfile.phone is NOT unique);
- family-shared-phone regression: two verified Patient users on one phone
  can never be resolved, and patient_access adds no linking by phone;
- MockSMSProvider refused outside TESTING (owner gate #6).
"""

from __future__ import annotations

import asyncio

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import (
    ERR_LOGIN_GENERIC,
    ERR_OTP_INVALID,
    PatientOtpError,
    PatientOtpService,
    normalize_phone,
)


def _configure_textbee_staging(monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.PATIENT_OTP_SMS_PROVIDER",
        "textbee",
    )
    monkeypatch.setattr("app.services.patient_otp_service.settings.ENV", "staging")
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_API_KEY", "staging-test-key"
    )
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_ALLOWED_RECIPIENT",
        "+998901112233",
    )


def test_memory_staging_reservation_is_atomic_and_token_scoped(svc):
    backend = svc.get_backend()
    key = "patotp:textbee-staging-cap:+998901112233"

    assert backend.reserve_once(key, "attempt-one", 60) is True
    assert backend.reserve_once(key, "attempt-two", 60) is False
    assert backend.release_if_value(key, "attempt-two") is False
    assert backend.get(key) == "attempt-one"
    assert backend.release_if_value(key, "attempt-one") is True
    assert backend.reserve_once(key, "attempt-two", 60) is True
    assert backend.get(key) == "attempt-two"


def test_redis_staging_reservation_uses_nx_and_compare_delete():
    from app.services.patient_otp_service import _RedisBackend

    class FakeRedis:
        def __init__(self):
            self.values = {}

        def set(self, key, value, *, ex, nx):
            assert ex == 60
            assert nx is True
            if key in self.values:
                return None
            self.values[key] = value
            return True

        def eval(self, script, key_count, key, value):
            assert key_count == 1
            assert "redis.call('GET'" in script
            if self.values.get(key) == value:
                del self.values[key]
                return 1
            return 0

    backend = _RedisBackend.__new__(_RedisBackend)
    backend._client = FakeRedis()
    backend._run = lambda operation, *args, **kwargs: operation(*args, **kwargs)
    key = "patotp:textbee-staging-cap:+998901112233"

    assert backend.reserve_once(key, "attempt-one", 60) is True
    assert backend.reserve_once(key, "attempt-two", 60) is False
    assert backend.release_if_value(key, "attempt-two") is False
    assert backend._client.values[key] == "attempt-one"
    assert backend.release_if_value(key, "attempt-one") is True
    assert backend.reserve_once(key, "attempt-two", 60) is True
    assert backend._client.values[key] == "attempt-two"


# ---------------------------------------------------------------- helpers
def _patient_user(
    db_session, *, username: str, phone: str | None, verified: bool = True
) -> User:
    user = User(
        username=username,
        email=f"{username}@test.local",
        full_name=username.title(),
        hashed_password=get_password_hash("Passw0rd!123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.flush()
    db_session.add(UserProfile(user_id=user.id, phone=phone, phone_verified=verified))
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def svc():
    service = PatientOtpService()
    service._reset_backend_for_tests()
    return service


@pytest.fixture()
def sms_ok(monkeypatch):
    """Stub SMS manager: capture messages, always succeed."""
    from types import SimpleNamespace

    sent: list[dict] = []

    async def fake_send(self=None, *, phone, text, provider_type=None, sender=None):
        sent.append({"phone": phone, "message": text})
        return SimpleNamespace(
            success=True, message_id="m1", provider="mock", error=None
        )

    from app.services import patient_otp_service as mod

    class _FakeManager:
        send_sms = staticmethod(fake_send)

    monkeypatch.setattr(mod, "get_sms_manager", lambda: _FakeManager())
    return sent


@pytest.mark.asyncio
async def test_staging_textbee_override_is_used_only_for_patient_otp(
    svc, sms_ok, monkeypatch
):
    from app.services import patient_otp_service as mod

    sent = []

    class FakeTextBee:
        def __init__(self, *, api_key, device_id=None):
            assert api_key == "staging-test-key"
            assert device_id is None

        async def send_sms(self, message):
            sent.append(message)
            return type(
                "Result",
                (),
                {"success": True, "message_id": "batch-1", "provider": "textbee"},
            )()

    monkeypatch.setattr(mod, "TextBeeSMSProvider", FakeTextBee)
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.PATIENT_OTP_SMS_PROVIDER",
        "textbee",
    )
    monkeypatch.setattr("app.services.patient_otp_service.settings.ENV", "staging")
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_API_KEY",
        "staging-test-key",
    )
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_ALLOWED_RECIPIENT",
        "+998901112233",
    )

    await svc.send_login_otp("+998901112233", "ru")

    assert len(sent) == 1
    assert sent[0].phone == "+998901112233"
    assert sent[0].text.startswith("Код входа: ")
    assert sms_ok == []

    # Even if the normal resend cooldown is cleared, this acceptance key can
    # queue at most one OTP during its 24-hour staging lease.
    svc.get_backend().delete("patotp:cd:+998901112233")
    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp("+998901112233", "ru")
    assert err.value.status_code == 429
    assert len(sent) == 1

    # The single-send acceptance limit is shared by login and activation OTPs.
    svc.get_backend().delete("patact:cd:+998901112233")
    with pytest.raises(PatientOtpError) as activation_err:
        await svc.send_activation_otp("+998901112233", "ru")
    assert activation_err.value.status_code == 429
    assert len(sent) == 1


@pytest.mark.asyncio
async def test_textbee_patient_otp_override_fails_closed_outside_staging(
    svc, sms_ok, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.PATIENT_OTP_SMS_PROVIDER",
        "textbee",
    )
    monkeypatch.setattr("app.services.patient_otp_service.settings.ENV", "production")

    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp("+998901112233", "ru")

    assert err.value.status_code == 503
    assert sms_ok == []


@pytest.mark.asyncio
async def test_textbee_patient_otp_override_fails_closed_without_key(
    svc, sms_ok, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.PATIENT_OTP_SMS_PROVIDER",
        "textbee",
    )
    monkeypatch.setattr("app.services.patient_otp_service.settings.ENV", "staging")
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_API_KEY", None
    )
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_ALLOWED_RECIPIENT",
        "+998901112233",
    )

    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp("+998901112233", "ru")

    assert err.value.status_code == 503
    assert sms_ok == []


@pytest.mark.asyncio
async def test_textbee_patient_otp_override_rejects_other_recipient(
    svc, sms_ok, monkeypatch
):
    from app.services import patient_otp_service as mod

    sends = []

    class FakeTextBee:
        def __init__(self, **kwargs):
            pass

        async def send_sms(self, message):
            sends.append(message)
            return type("Result", (), {"success": True, "provider": "textbee"})()

    monkeypatch.setattr(mod, "TextBeeSMSProvider", FakeTextBee)
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.PATIENT_OTP_SMS_PROVIDER",
        "textbee",
    )
    monkeypatch.setattr("app.services.patient_otp_service.settings.ENV", "staging")
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_API_KEY", "staging-test-key"
    )
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.TEXTBEE_ALLOWED_RECIPIENT",
        "+998901112233",
    )

    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp("+998901112244", "ru")

    assert err.value.status_code == 503
    assert sends == []
    assert sms_ok == []


@pytest.mark.asyncio
async def test_textbee_definite_rejection_releases_staging_send_reservation(
    svc, monkeypatch
):
    from app.services import patient_otp_service as mod

    _configure_textbee_staging(monkeypatch)
    sends = 0

    class FakeTextBee:
        def __init__(self, **kwargs):
            pass

        async def send_sms(self, message):
            nonlocal sends
            sends += 1
            if sends == 1:
                return type(
                    "Result",
                    (),
                    {
                        "success": False,
                        "provider": "textbee",
                        "definitely_not_accepted": True,
                    },
                )()
            return type(
                "Result",
                (),
                {"success": True, "provider": "textbee"},
            )()

    monkeypatch.setattr(mod, "TextBeeSMSProvider", FakeTextBee)

    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp("+998901112233", "ru")
    assert err.value.status_code == 503
    assert svc.get_backend().get("patotp:code:+998901112233") is None
    assert svc.get_backend().get("patotp:textbee-staging-cap:+998901112233") is None

    await svc.send_activation_otp("+998901112233", "ru")
    assert sends == 2
    assert svc.get_backend().get("patact:code:+998901112233") is not None
    assert svc.get_backend().get("patotp:textbee-staging-cap:+998901112233") is not None


@pytest.mark.asyncio
async def test_textbee_ambiguous_failure_keeps_staging_send_reservation(
    svc, monkeypatch
):
    from app.services import patient_otp_service as mod

    _configure_textbee_staging(monkeypatch)
    sends = 0

    class FakeTextBee:
        def __init__(self, **kwargs):
            pass

        async def send_sms(self, message):
            nonlocal sends
            sends += 1
            return type(
                "Result",
                (),
                {"success": False, "provider": "textbee"},
            )()

    monkeypatch.setattr(mod, "TextBeeSMSProvider", FakeTextBee)

    with pytest.raises(PatientOtpError) as first_err:
        await svc.send_login_otp("+998901112233", "ru")
    assert first_err.value.status_code == 503

    with pytest.raises(PatientOtpError) as retry_err:
        await svc.send_activation_otp("+998901112233", "ru")
    assert retry_err.value.status_code == 429
    assert sends == 1
    assert svc.get_backend().get("patotp:code:+998901112233") is None
    assert svc.get_backend().get("patact:code:+998901112233") is None


@pytest.mark.asyncio
async def test_textbee_concurrent_login_and_activation_share_reservation(
    svc, monkeypatch
):
    from app.services import patient_otp_service as mod

    _configure_textbee_staging(monkeypatch)
    started = asyncio.Event()
    finish_first = asyncio.Event()
    sends = 0

    class FakeTextBee:
        def __init__(self, **kwargs):
            pass

        async def send_sms(self, message):
            nonlocal sends
            sends += 1
            if sends == 1:
                started.set()
                await finish_first.wait()
                return type(
                    "Result",
                    (),
                    {
                        "success": False,
                        "provider": "textbee",
                        "definitely_not_accepted": True,
                    },
                )()
            return type(
                "Result",
                (),
                {"success": True, "provider": "textbee"},
            )()

    monkeypatch.setattr(mod, "TextBeeSMSProvider", FakeTextBee)

    first_attempt = asyncio.create_task(svc.send_login_otp("+998901112233", "ru"))
    await started.wait()
    with pytest.raises(PatientOtpError) as concurrent_err:
        await svc.send_activation_otp("+998901112233", "ru")
    assert concurrent_err.value.status_code == 429
    assert sends == 1

    finish_first.set()
    with pytest.raises(PatientOtpError) as first_err:
        await first_attempt
    assert first_err.value.status_code == 503

    await svc.send_activation_otp("+998901112233", "ru")
    assert sends == 2
    assert svc.get_backend().get("patact:code:+998901112233") is not None


# ------------------------------------------------------------ normalization
@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("+998901234567", "+998901234567"),
        ("+998 90 123 45 67", "+998901234567"),
        ("998901234567", None),
        ("+99890123456", None),
        ("+79991234567", None),
        ("", None),
        ("abc", None),
    ],
)
def test_normalize_phone_canonical(raw, expected):
    assert normalize_phone(raw) == expected


# ------------------------------------------------------------------ send
@pytest.mark.asyncio
async def test_send_login_otp_stores_hash_only_and_sends(svc, sms_ok, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    await svc.send_login_otp("+998 90 111 22 33", "ru")

    backend = svc._get_backend()
    stored = backend.get("patotp:code:+998901112233")
    assert stored is not None
    assert len(stored) == 64  # sha256 hex — plaintext code is never stored
    assert len(sms_ok) == 1
    assert sms_ok[0]["phone"] == "+998901112233"
    assert "Код входа:" in sms_ok[0]["message"]
    # TEST HOOK exposes the code only under TESTING
    code = backend.last_sent_code["+998901112233"]
    assert len(code) == 6


@pytest.mark.asyncio
async def test_send_login_otp_cooldown_and_hourly_cap(svc, sms_ok, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    phone = "+998901112233"
    await svc.send_login_otp(phone, "ru")
    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp(phone, "ru")
    assert err.value.status_code == 429  # cooldown

    backend = svc._get_backend()
    backend.delete("patotp:cd:" + phone)
    for _ in range(4):  # 1 initial + 4 = cap reached
        backend.delete("patotp:cd:" + phone)
        await svc.send_login_otp(phone, "ru")
    backend.delete("patotp:cd:" + phone)
    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp(phone, "ru")
    assert err.value.status_code == 429  # hourly cap


@pytest.mark.asyncio
async def test_mock_provider_refused_outside_testing(svc, sms_ok, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    monkeypatch.setenv("TESTING", "")  # simulate production
    svc._reset_backend_for_tests()
    with pytest.raises(PatientOtpError) as err:
        await svc.send_login_otp("+998901112233", "ru")
    assert err.value.status_code == 503
    assert sms_ok == []  # nothing sent


# ----------------------------------------------------------------- verify
@pytest.mark.asyncio
async def test_verify_grant_single_use(svc, sms_ok, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    phone = "+998901112233"
    await svc.send_login_otp(phone, "ru")
    code = svc._get_backend().last_sent_code[phone]

    result = svc.verify_login_otp(phone, code)
    grant = result["verification_grant"]
    assert svc.consume_grant(grant) == phone
    assert svc.consume_grant(grant) is None  # single-use


@pytest.mark.asyncio
async def test_verify_failures_share_one_generic_response(svc, sms_ok, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    phone = "+998901112233"
    await svc.send_login_otp(phone, "ru")
    code = svc._get_backend().last_sent_code[phone]

    with pytest.raises(PatientOtpError) as wrong:
        svc.verify_login_otp(phone, "000000" if code != "000000" else "111111")
    with pytest.raises(PatientOtpError) as missing:
        svc.verify_login_otp("+998909998877", code)
    with pytest.raises(PatientOtpError) as bad_format:
        svc.verify_login_otp(phone, "12ab56")

    assert wrong.value.detail == ERR_OTP_INVALID
    assert missing.value.detail == ERR_OTP_INVALID
    assert bad_format.value.detail == ERR_OTP_INVALID


@pytest.mark.asyncio
async def test_verify_attempts_exhaustion(svc, sms_ok, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    phone = "+998901112233"
    await svc.send_login_otp(phone, "ru")
    code = svc._get_backend().last_sent_code[phone]
    wrong = "000000" if code != "000000" else "111111"

    for _ in range(3):
        with pytest.raises(PatientOtpError):
            svc.verify_login_otp(phone, wrong)
    # even the CORRECT code is dead after exhaustion (code deleted)
    with pytest.raises(PatientOtpError):
        svc.verify_login_otp(phone, code)


# ----------------------------------------------------------------- resolver
def test_resolver_exactly_one_candidate(db_session):
    user = _patient_user(db_session, username="solo_patient", phone="+998901112233")
    svc = PatientOtpService()
    assert svc.resolve_patient_user_by_phone(db_session, "+998901112233").id == user.id


def test_resolver_zero_candidates_fail_closed(db_session):
    svc = PatientOtpService()
    assert svc.resolve_patient_user_by_phone(db_session, "+998901112233") is None


def test_resolver_family_shared_phone_fail_closed(db_session):
    """KEY regression: mother and child share one phone — resolver must
    refuse (2 candidates), never silently pick .first()."""
    _patient_user(db_session, username="mother", phone="+998901112233")
    _patient_user(db_session, username="child", phone="+998901112233")
    svc = PatientOtpService()
    assert svc.resolve_patient_user_by_phone(db_session, "+998901112233") is None


def test_resolver_ignores_unverified_and_inactive(db_session):
    _patient_user(
        db_session, username="unverified", phone="+998901112233", verified=False
    )
    svc = PatientOtpService()
    assert svc.resolve_patient_user_by_phone(db_session, "+998901112233") is None


def test_resolver_ignores_staff_role_on_same_phone(db_session):
    from app.core.security import get_password_hash as h
    from app.models.user import User as U

    staff = U(
        username="registrar_same_phone",
        email="rsp@test.local",
        hashed_password=h("Passw0rd!123"),
        role="Registrar",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(staff)
    db_session.flush()
    db_session.add(
        UserProfile(user_id=staff.id, phone="+998901112233", phone_verified=True)
    )
    db_session.commit()
    svc = PatientOtpService()
    assert svc.resolve_patient_user_by_phone(db_session, "+998901112233") is None


# ------------------------------------------------------------------- login
@pytest.mark.asyncio
async def test_login_with_grant_happy_path(svc, sms_ok, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    user = _patient_user(db_session, username="login_ok", phone="+998901112233")
    phone = "+998901112233"
    await svc.send_login_otp(phone, "ru")
    code = svc._get_backend().last_sent_code[phone]
    grant = svc.verify_login_otp(phone, code)["verification_grant"]

    payload = svc.login_with_grant(db_session, phone, grant)
    assert payload["token_type"] == "bearer"
    assert payload["access_token"]
    assert payload["user"]["id"] == user.id
    assert payload["user"]["role"] == "Patient"


@pytest.mark.asyncio
async def test_login_grant_phone_mismatch_generic_401(
    svc, sms_ok, monkeypatch, db_session
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    _patient_user(db_session, username="login_ok2", phone="+998901112233")
    await svc.send_login_otp("+998901112233", "ru")
    code = svc._get_backend().last_sent_code["+998901112233"]
    grant = svc.verify_login_otp("+998901112233", code)["verification_grant"]

    with pytest.raises(PatientOtpError) as err:
        svc.login_with_grant(db_session, "+998902222333", grant)
    assert err.value.status_code == 401
    assert err.value.detail == ERR_LOGIN_GENERIC


@pytest.mark.asyncio
async def test_login_ambiguous_phone_generic_401(svc, sms_ok, monkeypatch, db_session):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    _patient_user(db_session, username="mother2", phone="+998901112233")
    _patient_user(db_session, username="child2", phone="+998901112233")
    phone = "+998901112233"
    await svc.send_login_otp(phone, "ru")
    code = svc._get_backend().last_sent_code[phone]
    grant = svc.verify_login_otp(phone, code)["verification_grant"]

    with pytest.raises(PatientOtpError) as err:
        svc.login_with_grant(db_session, phone, grant)
    assert err.value.status_code == 401
    assert err.value.detail == ERR_LOGIN_GENERIC

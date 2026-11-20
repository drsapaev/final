"""Phase 0 PR-A1 — patient-access endpoints (integration).

API-level pass over the public OTP foundation: anti-enum response
uniformity over HTTP, grant flow, fail-closed login via the real
router/limiter/db wiring. Runs on the TESTING in-memory OTP backend.
"""

from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.two_factor_auth import TwoFactorAuth, TwoFactorBackupCode
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import get_patient_otp_service
from app.services.two_factor_service import get_two_factor_service

pytestmark = pytest.mark.asyncio

PHONE = "+998901112233"


def _patient_user(db_session, *, username: str, phone: str = PHONE) -> User:
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
    db_session.add(UserProfile(user_id=user.id, phone=phone, phone_verified=True))
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture()
def otp_backend():
    svc = get_patient_otp_service()
    svc._reset_backend_for_tests()
    backend = svc._get_backend()
    backend.last_sent_code.clear()
    return backend


async def test_request_otp_uniform_response(client, otp_backend, monkeypatch):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    resp = client.post(
        "/api/v1/patient-access/request-otp",
        json={"phone": "+998 90 111 22 33", "locale": "ru"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["success"] is True
    assert "Код" not in body["message"]  # no code in HTTP response
    # same number, second immediate call -> 429 (cooldown), number-neutral
    resp2 = client.post(
        "/api/v1/patient-access/request-otp", json={"phone": PHONE, "locale": "ru"}
    )
    assert resp2.status_code == 429


async def test_full_flow_request_verify_login(
    client, db_session, otp_backend, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    user = _patient_user(db_session, username="portal_user")

    r1 = client.post(
        "/api/v1/patient-access/request-otp", json={"phone": PHONE, "locale": "ru"}
    )
    assert r1.status_code == 200
    code = otp_backend.last_sent_code[PHONE]

    r2 = client.post(
        "/api/v1/patient-access/verify-otp", json={"phone": PHONE, "code": code}
    )
    assert r2.status_code == 200
    grant = r2.json()["verification_grant"]

    r3 = client.post(
        "/api/v1/patient-access/login",
        json={"phone": PHONE, "verification_grant": grant},
    )
    assert r3.status_code == 200
    body = r3.json()
    assert body["token_type"] == "bearer"
    assert body["user"]["id"] == user.id
    assert body["user"]["role"] == "Patient"

    # grant is single-use even over HTTP
    r4 = client.post(
        "/api/v1/patient-access/login",
        json={"phone": PHONE, "verification_grant": grant},
    )
    assert r4.status_code == 401


async def test_login_ambiguous_phone_generic_401_over_http(
    client, db_session, otp_backend, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    _patient_user(db_session, username="mother_http")
    _patient_user(db_session, username="child_http")

    client.post(
        "/api/v1/patient-access/request-otp", json={"phone": PHONE, "locale": "ru"}
    )
    code = otp_backend.last_sent_code[PHONE]
    r2 = client.post(
        "/api/v1/patient-access/verify-otp", json={"phone": PHONE, "code": code}
    )
    grant = r2.json()["verification_grant"]

    r3 = client.post(
        "/api/v1/patient-access/login",
        json={"phone": PHONE, "verification_grant": grant},
    )
    assert r3.status_code == 401
    assert "пациент" not in r3.json()["detail"].lower()  # no enumeration hints


async def test_request_otp_validation_rejects_bad_phone(client, otp_backend):
    resp = client.post(
        "/api/v1/patient-access/request-otp", json={"phone": "8-900-LEGACY"}
    )
    assert resp.status_code == 422


async def test_known_unknown_and_ambiguous_otp_responses_are_indistinguishable(
    client, db_session, otp_backend, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    known, unknown, ambiguous = "+998900000001", "+998900000002", "+998900000003"
    _patient_user(db_session, username="uniform_known", phone=known)
    _patient_user(db_session, username="uniform_ambiguous_a", phone=ambiguous)
    _patient_user(db_session, username="uniform_ambiguous_b", phone=ambiguous)
    request_results, verify_results, grants = [], [], []
    for phone in (known, unknown, ambiguous):
        requested = client.post(
            "/api/v1/patient-access/request-otp", json={"phone": phone}
        )
        assert requested.status_code == 200
        request_results.append(requested.json())
        verified = client.post(
            "/api/v1/patient-access/verify-otp",
            json={"phone": phone, "code": otp_backend.last_sent_code[phone]},
        )
        assert verified.status_code == 200
        body = verified.json()
        grants.append(body.pop("verification_grant"))
        verify_results.append(body)
    assert request_results[0] == request_results[1] == request_results[2]
    assert verify_results[0] == verify_results[1] == verify_results[2]
    for phone, grant, expected in zip(
        (known, unknown, ambiguous), grants, (200, 401, 401), strict=True
    ):
        response = client.post(
            "/api/v1/patient-access/login",
            json={"phone": phone, "verification_grant": grant},
        )
        assert response.status_code == expected


@pytest.mark.parametrize("factor", ["totp", "backup"])
async def test_sms_login_requires_second_factor_before_access(
    client, db_session, otp_backend, monkeypatch, factor
):
    import jwt

    from app.core.config import settings

    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    user = _patient_user(db_session, username="SYNTHETIC_sms_2fa")
    service = get_two_factor_service()
    secret = service.generate_totp_secret()
    twofa = TwoFactorAuth(
        user_id=user.id, totp_secret=secret, totp_enabled=True, totp_verified=True
    )
    db_session.add(twofa)
    db_session.flush()
    db_session.add(
        TwoFactorBackupCode(
            two_factor_auth_id=twofa.id, code=service._hash_backup_code("SYNTH123")
        )
    )
    db_session.commit()
    assert (
        client.post(
            "/api/v1/patient-access/request-otp", json={"phone": PHONE}
        ).status_code
        == 200
    )
    verification = client.post(
        "/api/v1/patient-access/verify-otp",
        json={"phone": PHONE, "code": otp_backend.last_sent_code[PHONE]},
    )
    login = client.post(
        "/api/v1/patient-access/login",
        json={
            "phone": PHONE,
            "verification_grant": verification.json()["verification_grant"],
        },
    )
    assert login.status_code == 200, login.text
    challenge = login.json()
    assert challenge["requires_2fa"] is True
    assert challenge["two_factor_method"] == "totp"
    assert not challenge.get("access_token") and not challenge.get("refresh_token")
    pending = challenge["pending_2fa_token"]
    replay = client.post(
        "/api/v1/patient-access/login",
        json={
            "phone": PHONE,
            "verification_grant": verification.json()["verification_grant"],
        },
    )
    assert replay.status_code == 401
    assert (
        client.get(
            "/api/v1/patients/", headers={"Authorization": f"Bearer {pending}"}
        ).status_code
        == 401
    )
    assert (
        client.post("/api/v1/2fa/setup", json={"enrollment_token": pending}).status_code
        == 401
    )
    rejected = client.post(
        "/api/v1/2fa/verify",
        json={"pending_2fa_token": pending, "recovery_token": "x" * 32},
    )
    assert rejected.status_code == 200 and rejected.json()["success"] is False
    bad = client.post(
        "/api/v1/2fa/verify",
        json={
            "pending_2fa_token": pending,
            "totp_code": "000000"
            if service.generate_totp_code(secret) != "000000"
            else "999999",
        },
    )
    assert bad.status_code == 200 and bad.json()["success"] is False
    payload = (
        {"totp_code": service.generate_totp_code(secret)}
        if factor == "totp"
        else {"backup_code": "SYNTH123"}
    )
    result = client.post(
        "/api/v1/2fa/verify",
        json={
            "pending_2fa_token": pending,
            "remember_device": True,
            "device_fingerprint": "x" * 40,
            **payload,
        },
    )
    assert result.status_code == 200, result.text
    body = result.json()
    assert body["success"] and body["access_token"] and not body.get("refresh_token")
    assert not body.get("session_token") and body["device_trusted"] is False
    claims = jwt.decode(
        body["access_token"], settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
    )
    assert claims["sub"] == str(user.id) and "scope" not in claims
    assert (
        client.post(
            "/api/v1/2fa/verify", json={"pending_2fa_token": pending, **payload}
        ).status_code
        == 401
    )


async def test_inconsistent_patient_2fa_state_fails_closed(
    client, db_session, otp_backend, monkeypatch
):
    monkeypatch.setattr(
        "app.services.patient_otp_service.settings.SMS_DEFAULT_PROVIDER", "mock"
    )
    user = _patient_user(db_session, username="SYNTHETIC_inconsistent_2fa")
    db_session.add(
        TwoFactorAuth(user_id=user.id, totp_enabled=True, totp_verified=False)
    )
    db_session.commit()
    assert (
        client.post(
            "/api/v1/patient-access/request-otp", json={"phone": PHONE}
        ).status_code
        == 200
    )
    verification = client.post(
        "/api/v1/patient-access/verify-otp",
        json={"phone": PHONE, "code": otp_backend.last_sent_code[PHONE]},
    )
    login = client.post(
        "/api/v1/patient-access/login",
        json={
            "phone": PHONE,
            "verification_grant": verification.json()["verification_grant"],
        },
    )
    assert login.status_code == 503 and not login.json().get("access_token")

"""Phase 0 PR-A1 — patient-access endpoints (integration).

API-level pass over the public OTP foundation: anti-enum response
uniformity over HTTP, grant flow, fail-closed login via the real
router/limiter/db wiring. Runs on the TESTING in-memory OTP backend.
"""

from __future__ import annotations

import pytest

from app.core.security import get_password_hash
from app.models.user import User
from app.models.user_profile import UserProfile
from app.services.patient_otp_service import get_patient_otp_service

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

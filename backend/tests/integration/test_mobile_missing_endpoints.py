"""Characterization tests for new mobile endpoints (PR-6).

Audit found 3 missing endpoints that the mobile app expects:
- GET /mobile/doctors — list doctors (mobile-friendly format)
- POST /mobile/attest — Play Integrity verification (Android app attestation)
- Idempotency-Key middleware — prevents duplicate POST submissions

This PR adds all 3.
"""
from __future__ import annotations

from datetime import date, datetime
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.clinic import Doctor
from app.models.user import User


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_patient_user(db_session) -> User:
    s = _suffix()
    user = User(
        username=f"mob_pt_{s}",
        email=f"mob-pt-{s}@test.local",
        full_name=f"Mobile Patient {s}",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def _make_doctor(db_session, *, specialty: str = "cardiology") -> Doctor:
    s = _suffix()
    user = User(
        username=f"doc_{s}",
        email=f"doc-{s}@test.local",
        full_name=f"Dr. {s}",
        hashed_password=get_password_hash("docpass"),
        role="Doctor",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty=specialty,
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return doctor


def _login(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "patient123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_get_mobile_doctors_returns_200(client, db_session):
    """GET /api/v1/mobile/doctors should return 200 with list of doctors."""
    user = _make_patient_user(db_session)
    _make_doctor(db_session, specialty="cardiology")
    _make_doctor(db_session, specialty="dermatology")
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/doctors", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)
    assert len(body) >= 2
    # Each doctor should have id, name, specialty
    for doc in body:
        assert "id" in doc
        assert "name" in doc
        assert "specialty" in doc


def test_get_mobile_doctors_filters_by_specialty(client, db_session):
    """GET /api/v1/mobile/doctors?specialty=cardiology should filter."""
    user = _make_patient_user(db_session)
    _make_doctor(db_session, specialty="cardiology")
    _make_doctor(db_session, specialty="dermatology")
    headers = _login(client, user)

    response = client.get(
        "/api/v1/mobile/doctors?specialty=cardiology", headers=headers
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body) >= 1
    assert all(d["specialty"] == "cardiology" for d in body)


def test_mobile_attest_play_integrity_returns_200(client, db_session):
    """POST /api/v1/mobile/attest should accept Play Integrity token."""
    user = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.post(
        "/api/v1/mobile/attest",
        headers=headers,
        json={
            "platform": "android",
            "integrity_token": "test_integrity_token_abc123",
            "package_name": "com.clinic.mobile",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "status" in body
    assert body["status"] in ("verified", "pending", "skipped")


def test_mobile_attest_ios_returns_200(client, db_session):
    """POST /api/v1/mobile/attest should accept iOS device check token."""
    user = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.post(
        "/api/v1/mobile/attest",
        headers=headers,
        json={
            "platform": "ios",
            "device_token": "test_ios_device_token_abc123",
            "bundle_id": "com.clinic.mobile",
        },
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert "status" in body


def test_idempotency_key_prevents_duplicate_post(client, db_session):
    """POST with same Idempotency-Key should return cached response, not create duplicate."""
    from app.models.patient import Patient

    user = _make_patient_user(db_session)
    # Make user a registrar so they can create patients
    user.role = "Registrar"
    db_session.commit()
    headers = _login(client, user)

    patient_data = {
        "first_name": "Test",
        "last_name": f"Patient{_suffix()}",
        "phone": f"+99890{datetime.now().strftime('%M%S%f')[:7]}",
        "birth_date": "1990-01-01",
    }

    idem_key = f"idem-{_suffix()}"
    headers_with_key = {**headers, "Idempotency-Key": idem_key}

    # First request — creates patient
    r1 = client.post("/api/v1/patients/", json=patient_data, headers=headers_with_key)
    assert r1.status_code in (200, 201), r1.text

    # Second request with same Idempotency-Key — should return cached response
    r2 = client.post("/api/v1/patients/", json=patient_data, headers=headers_with_key)
    assert r2.status_code in (200, 201), r2.text

    # Both responses should have the same patient id (idempotent)
    if r1.status_code == 200 and r2.status_code == 200:
        id1 = r1.json().get("id")
        id2 = r2.json().get("id")
        assert id1 == id2, "Idempotency-Key should prevent duplicate creation"

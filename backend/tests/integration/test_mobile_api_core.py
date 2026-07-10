"""Characterization tests for the core mobile_api.py endpoints (PR-3).

Audit found that several endpoints in mobile_api.py return HTTP 500 due to
schema/model drift:

- /patients/me uses Patient.fio / Patient.birth_year / Patient.telegram_id
  which don't exist on the Patient model (real columns: first_name,
  last_name, middle_name, birth_date, and telegram_id is on User).
- /appointments/upcoming and /appointments/{id} access appointment.doctor
  relationship (doesn't exist on Appointment) and appointment.doctor.name
  (Doctor has no `name`; name is on User.full_name via doctor.user).
- /appointments/book looks up doctor via crud_user.get_user, but doctors
  are in the doctors table, not users; it also reads doctor.name / doctor.
  specialty from the User object (User has no specialty).
- /lab/results reads result.test_name / result.result / result.normal_range
  / result.unit / result.test_date / result.status / result.doctor_notes —
  verify these exist on the LabResult model.

This file asserts 200 (not 500) for each endpoint.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_patient_user(db_session) -> tuple[User, Patient]:
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

    patient = Patient(
        user_id=user.id,
        first_name="Patient",
        last_name=f"Test{s}",
        phone=f"+99890{s[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def _make_doctor(db_session) -> Doctor:
    s = _suffix()
    # Doctor requires a User for name lookup
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
        specialty="cardiology",
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


def test_get_mobile_patient_profile_returns_200(client, db_session):
    """GET /api/v1/mobile/patients/me should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/patients/me", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "id" in body
    assert "fio" in body
    assert "phone" in body


def test_get_upcoming_appointments_returns_200(client, db_session):
    """GET /api/v1/mobile/appointments/upcoming should return 200, not 500."""
    user, patient = _make_patient_user(db_session)
    doctor = _make_doctor(db_session)
    # Seed an upcoming appointment
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today() + timedelta(days=3),
        status="scheduled",
    )
    db_session.add(appt)
    db_session.commit()

    headers = _login(client, user)
    response = client.get("/api/v1/mobile/appointments/upcoming", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)


def test_get_appointment_detail_returns_200(client, db_session):
    """GET /api/v1/mobile/appointments/{id} should return 200, not 500."""
    user, patient = _make_patient_user(db_session)
    doctor = _make_doctor(db_session)
    appt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today() + timedelta(days=3),
        status="scheduled",
    )
    db_session.add(appt)
    db_session.commit()
    db_session.refresh(appt)

    headers = _login(client, user)
    response = client.get(f"/api/v1/mobile/appointments/{appt.id}", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["id"] == appt.id
    assert "doctor_name" in body


def test_get_lab_results_returns_200(client, db_session):
    """GET /api/v1/mobile/lab/results should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/lab/results", headers=headers)

    # Empty list is fine — we just need 200, not 500.
    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)


def test_get_mobile_quick_stats_returns_200(client, db_session):
    """GET /api/v1/mobile/stats should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/stats", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert "total_appointments" in body


def test_get_mobile_notifications_returns_200(client, db_session):
    """GET /api/v1/mobile/notifications should return 200, not 500."""
    user, _ = _make_patient_user(db_session)
    headers = _login(client, user)

    response = client.get("/api/v1/mobile/notifications", headers=headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert isinstance(body, list)

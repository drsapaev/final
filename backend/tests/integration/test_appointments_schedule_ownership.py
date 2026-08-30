"""Ownership tests for GET /appointments/doctor/{doctor_id}/schedule.

Contract (PR: fix/appointments-schedule-ownership):
- Admin/Registrar (+superuser): any doctor's schedule;
- doctor-capable roles (Doctor + legacy variants): only their own doctor_id
  — Doctor A must NOT be able to read Doctor B's schedule by substituting
  doctor_id (patient_id + reason leak otherwise);
- Patient and every other authenticated role: denied.

Regression for the HIGH-risk IDOR gap found in the ownership audit (the
endpoint previously accepted any authenticated user with no ownership check).
"""
from __future__ import annotations

from datetime import date, timedelta

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User


def _doctor_pair(db_session, label_a: str, label_b: str) -> tuple[User, Doctor, User, Doctor]:
    rows = []
    for label in (label_a, label_b):
        user = User(
            username=f"sched_{label}",
            email=f"sched-{label}@test.com",
            full_name=f"Schedule {label}",
            hashed_password=get_password_hash("secret123"),
            role="Doctor",
            is_active=True,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        doctor = Doctor(user_id=user.id, specialty="stomatology", active=True)
        db_session.add(doctor)
        db_session.commit()
        db_session.refresh(doctor)
        rows.append((user, doctor))
    return rows[0][0], rows[0][1], rows[1][0], rows[1][1]


def _schedule_appointment(db_session, doctor: Doctor, patient: Patient) -> Appointment:
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today() + timedelta(days=1),
        appointment_time="10:00",
        status="scheduled",
        notes="private reason",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


def _headers_for(user: User) -> dict[str, str]:
    """Mint an access token the same way conftest's auth_headers fixture does."""
    from tests.conftest import mint_access_token

    return {"Authorization": f"Bearer {mint_access_token(user)}"}


def _patient(db_session) -> Patient:
    patient = Patient(
        first_name="Sched",
        last_name="Patient",
        phone="+998900001122",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def test_doctor_cannot_read_other_doctor_schedule(client, db_session):
    user_a, _doctor_a, _user_b, doctor_b = _doctor_pair(db_session, "a", "b")
    patient = _patient(db_session)
    _schedule_appointment(db_session, doctor_b, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_b.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user_a),
    )
    assert response.status_code == 403, response.text


def test_doctor_reads_own_schedule(client, db_session):
    user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "own_a", "own_b")
    patient = _patient(db_session)
    appointment = _schedule_appointment(db_session, doctor_a, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(user_a),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    entries = body if isinstance(body, list) else body.get("appointments", body.get("schedule", []))
    assert any(entry.get("id") == appointment.id for entry in entries)


def test_registrar_reads_any_doctor_schedule(client, db_session, registrar_user):
    _user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "reg_a", "reg_b")
    patient = _patient(db_session)
    appointment = _schedule_appointment(db_session, doctor_a, patient)

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(registrar_user),
    )
    assert response.status_code == 200, response.text
    body = response.json()
    entries = body if isinstance(body, list) else body.get("appointments", body.get("schedule", []))
    assert any(entry.get("id") == appointment.id for entry in entries)


def test_patient_denied_doctor_schedule(client, db_session):
    _user_a, doctor_a, _user_b, _doctor_b = _doctor_pair(db_session, "pat_a", "pat_b")
    patient_user = User(
        username="sched_patient",
        email="sched-patient@test.com",
        full_name="Sched Patient User",
        hashed_password=get_password_hash("secret123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(patient_user)
    db_session.commit()

    response = client.get(
        f"/api/v1/appointments/doctor/{doctor_a.id}/schedule",
        params={"date": str(date.today() + timedelta(days=1))},
        headers=_headers_for(patient_user),
    )
    assert response.status_code == 403, response.text

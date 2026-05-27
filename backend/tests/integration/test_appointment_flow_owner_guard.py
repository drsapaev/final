from __future__ import annotations

from datetime import date
from uuid import uuid4

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User
from app.models.visit import Visit


def _suffix() -> str:
    return uuid4().hex[:10]


def _create_doctor_user(db_session, *, label: str) -> tuple[User, Doctor]:
    suffix = _suffix()
    user = User(
        username=f"appt_flow_{label}_{suffix}",
        email=f"appt-flow-{label}-{suffix}@test.local",
        full_name=f"Appointment Flow {label}",
        hashed_password=get_password_hash("doctor123"),
        role="Doctor",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    doctor = Doctor(
        user_id=user.id,
        specialty="therapy",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    return user, doctor


def _create_patient(db_session, *, label: str) -> Patient:
    suffix = _suffix()
    patient = Patient(
        first_name=f"Patient {label}",
        last_name="OwnerGuard",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return patient


def _create_appointment(db_session, *, patient: Patient, doctor: Doctor) -> Appointment:
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=date.today(),
        appointment_time="10:00",
        status="paid",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)
    return appointment


def _doctor_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_doctor_cannot_read_other_doctor_appointment_flow_status(
    client,
    db_session,
) -> None:
    own_user, _own_doctor = _create_doctor_user(db_session, label="own")
    _other_user, other_doctor = _create_doctor_user(db_session, label="other")
    other_patient = _create_patient(db_session, label="other")
    other_appointment = _create_appointment(
        db_session,
        patient=other_patient,
        doctor=other_doctor,
    )
    headers = _doctor_headers(client, own_user)

    other_response = client.get(
        f"/api/v1/appointments/{other_appointment.id}/status",
        headers=headers,
    )
    assert other_response.status_code == 403

    leaked_visit = (
        db_session.query(Visit)
        .filter(
            Visit.patient_id == other_patient.id,
            Visit.doctor_id == other_doctor.id,
        )
        .first()
    )
    assert leaked_visit is None

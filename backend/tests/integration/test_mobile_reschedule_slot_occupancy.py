"""Mobile patient reschedule must respect slot occupancy (PR-0b).

POST /api/v1/mobile/appointments/reschedule previously wrote the new
date/time with no occupancy check and no per-doctor lock (the write happens
in ``crud_appointment.reschedule_appointment``), so a mobile patient could
land on an already-booked slot and two concurrent reschedules could
double-book. Ordering follows the documented writer contract in
``app/services/appointment_slot_guard.py``: the FOR UPDATE doctor lock is
taken BEFORE the occupancy pre-check. The doctor is fixed on this endpoint
(no reassignment), so no eligibility check - same rule as PUT
/appointments/{id}.
"""

from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.user import User

RESCHEDULE_URL = "/api/v1/mobile/appointments/reschedule"


@pytest.fixture
def reschedule_setup(db_session):
    """Patient user linked to a Patient row, one Doctor, two appointments."""
    user = User(
        username="mobile_resched_patient",
        email="mobile_resched_patient@test.com",
        full_name="Тест Мобайл Перенос",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        first_name="Тест",
        last_name="МобайлПеренос",
        phone="+998900000099",
        birth_date=date(1990, 1, 1),
        user_id=user.id,
    )
    db_session.add(patient)

    doctor = Doctor(specialty="cardiology", active=True)
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(patient)
    db_session.refresh(doctor)

    base_day = date.today() + timedelta(days=5)
    apt = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=base_day,
        appointment_time="10:00",
        status="scheduled",
    )
    other = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=base_day,
        appointment_time="14:00",
        status="scheduled",
    )
    db_session.add_all([apt, other])
    db_session.commit()
    db_session.refresh(apt)
    return {
        "user": user,
        "patient": patient,
        "doctor": doctor,
        "apt": apt,
        "other": other,
        "base_day": base_day,
    }


@pytest.fixture
def patient_headers(client: TestClient, reschedule_setup):
    """Patient-role login (no 2FA for Patient role)."""
    user = reschedule_setup["user"]
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "patient123"},
    )
    assert response.status_code == 200, response.text
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_reschedule_onto_occupied_slot_is_rejected(
    client: TestClient, reschedule_setup, patient_headers
):
    """RED-first: moving onto a slot already booked with the same doctor must 409."""
    apt = reschedule_setup["apt"]
    response = client.post(
        RESCHEDULE_URL,
        headers=patient_headers,
        json={
            "appointment_id": apt.id,
            "new_date": reschedule_setup["base_day"].isoformat(),
            "new_time": "14:00",  # occupied by the second appointment
        },
    )
    assert response.status_code == 409, response.text
    assert "занято" in response.json()["detail"]


def test_reschedule_to_free_slot_succeeds(
    client: TestClient, reschedule_setup, patient_headers, db_session
):
    apt = reschedule_setup["apt"]
    free_day = (date.today() + timedelta(days=6)).isoformat()
    response = client.post(
        RESCHEDULE_URL,
        headers=patient_headers,
        json={"appointment_id": apt.id, "new_date": free_day, "new_time": "15:00"},
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True

    db_session.refresh(apt)
    assert apt.appointment_date.isoformat() == free_day
    assert apt.appointment_time == "15:00"


def test_reschedule_onto_own_current_slot_passes(
    client: TestClient, reschedule_setup, patient_headers
):
    """exclude_appointment_id: re-saving the own slot is not a conflict."""
    apt = reschedule_setup["apt"]
    response = client.post(
        RESCHEDULE_URL,
        headers=patient_headers,
        json={
            "appointment_id": apt.id,
            "new_date": reschedule_setup["base_day"].isoformat(),
            "new_time": "10:00",  # the appointment's own current slot
        },
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True

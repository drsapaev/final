"""Characterization tests for the 14 broken endpoints in mobile_api_extended.py.

PR-1 of the backend audit remediation. These tests hit each broken endpoint
with valid input and assert a 200 response. Before the fix all 14 endpoints
returned HTTP 500 (the RED state). After Phase 1-3 fixes they should all
return 200 (the GREEN state).

Audit report: /home/z/my-project/download/AUDIT_PR1_MOBILE_EXTENDED.md
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, time
from uuid import uuid4

import pytest

from app.core.security import get_password_hash
from app.models.appointment import Appointment
from app.models.clinic import Doctor, Schedule, ServiceCategory
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User


def _suffix() -> str:
    return uuid4().hex[:10]


def _make_patient_user(db_session, *, label: str = "mob") -> tuple[User, Patient]:
    """Create a Patient user + linked Patient profile and return both."""
    suffix = _suffix()
    user = User(
        username=f"mob_pt_{label}_{suffix}",
        email=f"mob-pt-{label}-{suffix}@test.local",
        full_name=f"Mobile Patient {label}",
        hashed_password=get_password_hash("patient123"),
        role="Patient",
        is_active=True,
        is_superuser=False,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    patient = Patient(
        user_id=user.id,
        first_name=f"Patient {label}",
        last_name="Mobile",
        phone=f"+99890{suffix[:7]}",
        birth_date=date(1990, 1, 1),
    )
    db_session.add(patient)
    db_session.commit()
    db_session.refresh(patient)
    return user, patient


def _patient_headers(client, user: User) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "patient123"},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _make_doctor(db_session, *, label: str = "mob") -> Doctor:
    suffix = _suffix()
    user = User(
        username=f"mob_dr_{label}_{suffix}",
        email=f"mob-dr-{label}-{suffix}@test.local",
        full_name=f"Dr Mobile {label}",
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
    return doctor


# ==================== 1. POST /doctors/search ====================


def test_search_doctors_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="search")
    headers = _patient_headers(client, user)

    response = client.post(
        "/api/v1/mobile/doctors/search",
        json={"specialty": None, "name": None, "limit": 5},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "doctors" in payload
    assert "total_found" in payload


# ==================== 2. GET /doctors/{id}/schedule ====================


def test_get_doctor_schedule_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="sched")
    headers = _patient_headers(client, user)
    doctor = _make_doctor(db_session, label="sched")

    today = date.today()
    date_from = today.isoformat()
    date_to = (today + timedelta(days=7)).isoformat()

    response = client.get(
        f"/api/v1/mobile/doctors/{doctor.id}/schedule",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["doctor_id"] == doctor.id
    assert "schedule" in payload


# ==================== 3. POST /services/search ====================


def test_search_services_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="svc")
    headers = _patient_headers(client, user)

    response = client.post(
        "/api/v1/mobile/services/search",
        json={"category": None, "name": None, "limit": 5},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "services" in payload
    assert "total_found" in payload


# ==================== 4. GET /services/categories ====================


def test_get_service_categories_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="cat")
    headers = _patient_headers(client, user)

    # Seed a category so the response has at least one row.
    category = ServiceCategory(
        code=f"MOB_{_suffix()}",
        name_ru="Мобильная категория",
        specialty="therapy",
        active=True,
    )
    db_session.add(category)
    db_session.commit()
    db_session.refresh(category)

    response = client.get(
        "/api/v1/mobile/services/categories",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "categories" in payload


# ==================== 5. GET /queues/status ====================


def test_get_queues_status_returns_200(client, db_session) -> None:
    from app.models.online_queue import DailyQueue

    user, _patient = _make_patient_user(db_session, label="qst")
    headers = _patient_headers(client, user)
    doctor = _make_doctor(db_session, label="qst")

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    response = client.get(
        "/api/v1/mobile/queues/status",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "queues" in payload
    assert "last_updated" in payload


# ==================== 6. GET /queues/my-position ====================


def test_get_my_queue_position_returns_200(client, db_session) -> None:
    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    user, patient = _make_patient_user(db_session, label="qpos")
    headers = _patient_headers(client, user)
    doctor = _make_doctor(db_session, label="qpos")

    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_id=patient.id,
        patient_name=patient.short_name(),
        phone=patient.phone,
        source="online",
        status="waiting",
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)

    response = client.get(
        "/api/v1/mobile/queues/my-position",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "positions" in payload


# ==================== 7. POST /appointments/cancel ====================


def test_cancel_appointment_returns_200(client, db_session) -> None:
    user, patient = _make_patient_user(db_session, label="cancel")
    headers = _patient_headers(client, user)
    doctor = _make_doctor(db_session, label="cancel")

    # Appointment must be more than 2 hours in the future for the cancel
    # check to pass.
    future_date = date.today() + timedelta(days=1)
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=future_date,
        appointment_time="10:00",
        status="scheduled",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    response = client.post(
        "/api/v1/mobile/appointments/cancel",
        json={"appointment_id": appointment.id, "reason": "test cancel"},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


# ==================== 8. POST /appointments/reschedule ====================


def test_reschedule_appointment_returns_200(client, db_session) -> None:
    user, patient = _make_patient_user(db_session, label="resched")
    headers = _patient_headers(client, user)
    doctor = _make_doctor(db_session, label="resched")

    # Appointment must be more than 4 hours in the future for the reschedule
    # check to pass.
    future_date = date.today() + timedelta(days=2)
    appointment = Appointment(
        patient_id=patient.id,
        doctor_id=doctor.id,
        appointment_date=future_date,
        appointment_time="10:00",
        status="scheduled",
    )
    db_session.add(appointment)
    db_session.commit()
    db_session.refresh(appointment)

    new_date = (date.today() + timedelta(days=5)).isoformat()
    response = client.post(
        "/api/v1/mobile/appointments/reschedule",
        json={
            "appointment_id": appointment.id,
            "new_date": new_date,
            "new_time": "11:30",
            "reason": "test reschedule",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


# ==================== 9. POST /feedback ====================


def test_submit_feedback_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="fb")
    headers = _patient_headers(client, user)

    response = client.post(
        "/api/v1/mobile/feedback",
        json={
            "type": "review",
            "rating": 5,
            "message": "Отличная клиника!",
            "appointment_id": None,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


# ==================== 10. POST /emergency/contact ====================


def test_emergency_contact_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="emrg")
    headers = _patient_headers(client, user)

    response = client.post(
        "/api/v1/mobile/emergency/contact",
        json={
            "type": "clinic",
            "message": "Test emergency",
            "location": {"lat": 41.0, "lng": 69.0},
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


# ==================== 11. PUT /profile ====================


def test_update_profile_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="prof")
    headers = _patient_headers(client, user)

    response = client.put(
        "/api/v1/mobile/profile",
        json={
            "full_name": "Updated Name",
            "birth_date": "1985-05-05",
            "address": "New Address",
            "emergency_contact": "+998901234567",
            "allergies": "Penicillin",
            "chronic_conditions": "Asthma",
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


# ==================== 12. POST /profile/avatar ====================


def test_upload_avatar_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="avatar")
    headers = _patient_headers(client, user)

    response = client.post(
        "/api/v1/mobile/profile/avatar",
        files={
            "file": ("avatar.png", b"\x89PNG\r\n\x1a\nfake-png-bytes", "image/png"),
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True
    assert "avatar_url" in response.json()


# ==================== 13. PUT /settings/notifications ====================


def test_update_notification_settings_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="nsu")
    headers = _patient_headers(client, user)

    response = client.put(
        "/api/v1/mobile/settings/notifications",
        json={
            "push_enabled": True,
            "sms_enabled": False,
            "email_enabled": True,
            "appointment_reminders": True,
            "lab_results": True,
            "promotions": False,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    assert response.json()["success"] is True


# ==================== 14. GET /settings/notifications ====================


def test_get_notification_settings_returns_200(client, db_session) -> None:
    user, _patient = _make_patient_user(db_session, label="nsg")
    headers = _patient_headers(client, user)

    response = client.get(
        "/api/v1/mobile/settings/notifications",
        headers=headers,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert "push_enabled" in payload
    assert "sms_enabled" in payload

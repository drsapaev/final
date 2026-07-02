from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.user import User


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _login_headers(client: TestClient, *, user: User, password: str) -> dict[str, str]:
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": password},
    )
    assert response.status_code == 200
    return _auth_headers(response.json()["access_token"])


def _seed_legacy_today_queue(
    db_session: Session,
    test_doctor: Doctor,
    test_patient: Patient,
) -> DailyQueue:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="registrar",
        status="waiting",
        created_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(queue)
    return queue


def _seed_legacy_call_entry(
    db_session: Session,
    *,
    doctor: Doctor,
    patient: Patient,
) -> OnlineQueueEntry:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor.id,
        queue_tag="cardiology_common",
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
        source="registrar",
        status="waiting",
        created_at=datetime.utcnow(),
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


def test_registrar_can_read_legacy_today_queue(
    client: TestClient,
    db_session: Session,
    registrar_token: str,
    test_doctor: Doctor,
    test_patient: Patient,
) -> None:
    queue = _seed_legacy_today_queue(db_session, test_doctor, test_patient)

    response = client.get(
        "/api/v1/queue/legacy/today",
        headers=_auth_headers(registrar_token),
        params={"specialist_id": test_doctor.id},
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["queue_id"] == queue.id
    assert payload["entries"][0]["patient_name"] == test_patient.short_name()
    assert payload["entries"][0]["phone"] == test_patient.phone


def test_patient_cannot_read_legacy_today_queue(
    client: TestClient,
    db_session: Session,
    patient_token: str,
    test_doctor: Doctor,
    test_patient: Patient,
) -> None:
    _seed_legacy_today_queue(db_session, test_doctor, test_patient)

    response = client.get(
        "/api/v1/queue/legacy/today",
        headers=_auth_headers(patient_token),
        params={"specialist_id": test_doctor.id},
    )

    assert response.status_code == 403


def test_registrar_can_call_legacy_queue_entry(
    client: TestClient,
    db_session: Session,
    registrar_token: str,
    test_doctor: Doctor,
    test_patient: Patient,
) -> None:
    entry = _seed_legacy_call_entry(
        db_session,
        doctor=test_doctor,
        patient=test_patient,
    )

    response = client.post(
        f"/api/v1/queue/legacy/call/{entry.id}",
        headers=_auth_headers(registrar_token),
    )

    assert response.status_code == 200, response.text
    db_session.refresh(entry)
    assert entry.status == "called"
    assert entry.called_at is not None


def test_doctor_can_call_own_legacy_queue_entry_by_linked_doctor_id(
    client: TestClient,
    db_session: Session,
    test_doctor_user: User,
    test_patient: Patient,
) -> None:
    doctor = Doctor(
        user_id=test_doctor_user.id,
        specialty="cardiology",
        active=True,
    )
    db_session.add(doctor)
    db_session.commit()
    db_session.refresh(doctor)
    entry = _seed_legacy_call_entry(
        db_session,
        doctor=doctor,
        patient=test_patient,
    )

    response = client.post(
        f"/api/v1/queue/legacy/call/{entry.id}",
        headers=_login_headers(client, user=test_doctor_user, password="doctor123"),
    )

    assert response.status_code == 200, response.text
    db_session.refresh(entry)
    assert entry.status == "called"


def test_doctor_cannot_call_legacy_queue_when_only_user_id_matches_specialist_id(
    client: TestClient,
    db_session: Session,
    test_doctor_user: User,
    test_patient: Patient,
) -> None:
    foreign_doctor = Doctor(
        id=test_doctor_user.id,
        specialty="foreign",
        active=True,
    )
    db_session.add(foreign_doctor)
    db_session.commit()
    db_session.refresh(foreign_doctor)

    actor_doctor = Doctor(
        user_id=test_doctor_user.id,
        specialty="cardiology",
        active=True,
    )
    db_session.add(actor_doctor)
    db_session.commit()
    db_session.refresh(actor_doctor)
    assert actor_doctor.id != test_doctor_user.id

    entry = _seed_legacy_call_entry(
        db_session,
        doctor=foreign_doctor,
        patient=test_patient,
    )

    response = client.post(
        f"/api/v1/queue/legacy/call/{entry.id}",
        headers=_login_headers(client, user=test_doctor_user, password="doctor123"),
    )

    assert response.status_code == 403
    db_session.refresh(entry)
    assert entry.status == "waiting"
    assert entry.called_at is None

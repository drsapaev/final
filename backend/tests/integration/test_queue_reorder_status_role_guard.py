from __future__ import annotations

from datetime import date, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_queue_with_patient(
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


def test_registrar_can_read_queue_reorder_status(
    client: TestClient,
    db_session: Session,
    registrar_token: str,
    test_doctor: Doctor,
    test_patient: Patient,
) -> None:
    queue = _seed_queue_with_patient(db_session, test_doctor, test_patient)

    response = client.get(
        f"/api/v1/queue/reorder/status/{queue.id}",
        headers=_auth_headers(registrar_token),
    )

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["queue_id"] == queue.id
    assert payload["entries"][0]["patient_name"] == test_patient.short_name()
    assert payload["entries"][0]["phone"] == test_patient.phone


def test_patient_cannot_read_queue_reorder_status_by_queue_id(
    client: TestClient,
    db_session: Session,
    patient_token: str,
    test_doctor: Doctor,
    test_patient: Patient,
) -> None:
    queue = _seed_queue_with_patient(db_session, test_doctor, test_patient)

    response = client.get(
        f"/api/v1/queue/reorder/status/{queue.id}",
        headers=_auth_headers(patient_token),
    )

    assert response.status_code == 403


def test_patient_cannot_read_queue_reorder_status_by_specialist(
    client: TestClient,
    db_session: Session,
    patient_token: str,
    test_doctor: Doctor,
    test_patient: Patient,
) -> None:
    _seed_queue_with_patient(db_session, test_doctor, test_patient)

    response = client.get(
        "/api/v1/queue/reorder/status/by-specialist/",
        headers=_auth_headers(patient_token),
        params={"specialist_id": test_doctor.id, "day": date.today().isoformat()},
    )

    assert response.status_code == 403

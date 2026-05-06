from __future__ import annotations

from datetime import date

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.service import Service
from app.services.batch_patient_service import (
    BatchPatientService,
    BatchUpdateRequest,
    EntryAction,
)
from app.services.service_mapping import normalize_service_code


def _create_batch_service(
    db_session,
    *,
    service_code: str,
    doctor_id: int | None,
    queue_tag: str = "cardiology",
) -> Service:
    service = Service(
        code=service_code,
        service_code=service_code,
        name=f"Service {service_code}",
        active=True,
        queue_tag=queue_tag,
        doctor_id=doctor_id,
        requires_doctor=doctor_id is not None,
    )
    db_session.add(service)
    db_session.commit()
    db_session.refresh(service)
    return service


def _create_existing_entry(
    db_session,
    *,
    patient_id: int,
    doctor_id: int,
    number: int,
    queue_tag: str,
    status: str = "waiting",
    source: str = "desk",
) -> OnlineQueueEntry:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=doctor_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)

    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_id=patient_id,
        patient_name="Characterization Patient",
        phone="+998901234567",
        source=source,
        status=status,
    )
    db_session.add(entry)
    db_session.commit()
    db_session.refresh(entry)
    return entry


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_create_action_characterization_mounted_path_creates_queue_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    service = _create_batch_service(
        db_session,
        service_code="W2C-BATCH-CREATE",
        doctor_id=test_doctor.id,
        queue_tag="cardiology",
    )
    target_day = date.today().isoformat()

    response = client.patch(
        f"/api/v1/registrar/batch/patients/{test_patient.id}/entries/{target_day}",
        headers=registrar_auth_headers,
        json={
            "entries": [
                {
                    "action": "create",
                    "specialty": "cardiology",
                    "service_code": service.service_code,
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["updated_entries"][0]["status"] == "created"

    created_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.id.asc())
        .all()
    )
    assert len(created_entries) == 1
    assert created_entries[0].source == "batch_update"
    assert created_entries[0].status == "waiting"
    assert created_entries[0].number == 1
    assert created_entries[0].service_codes == [normalize_service_code(service.service_code)]
    assert created_entries[0].queue_time is not None

    created_queue = (
        db_session.query(DailyQueue)
        .filter(DailyQueue.id == created_entries[0].queue_id)
        .first()
    )
    assert created_queue is not None
    assert created_queue.specialist_id == test_doctor.id
    assert created_queue.queue_tag == service.queue_tag


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_create_action_characterization_service_path_returns_created_entry(
    db_session,
    test_patient,
    test_doctor,
):
    service = _create_batch_service(
        db_session,
        service_code="W2C-BATCH-CREATE-SVC",
        doctor_id=test_doctor.id,
        queue_tag="cardiology",
    )
    batch_service = BatchPatientService(db_session)

    result = batch_service.batch_update(
        patient_id=test_patient.id,
        target_date=date.today(),
        request=BatchUpdateRequest(
            entries=[
                EntryAction(
                    action="create",
                    specialty="cardiology",
                    service_code=service.service_code,
                )
            ]
        ),
    )

    assert result.success is True
    assert len(result.updated_entries) == 1
    assert result.updated_entries[0].status == "created"

    created_entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.id == result.updated_entries[0].id)
        .first()
    )
    assert created_entry is not None
    assert created_entry.source == "batch_update"
    assert created_entry.service_codes == [normalize_service_code(service.service_code)]


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_create_action_characterization_duplicate_scenario_creates_next_number(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    test_doctor,
):
    service = _create_batch_service(
        db_session,
        service_code="W2C-BATCH-DUP",
        doctor_id=test_doctor.id,
        queue_tag="cardiology",
    )
    existing_entry = _create_existing_entry(
        db_session,
        patient_id=test_patient.id,
        doctor_id=test_doctor.id,
        number=8,
        queue_tag="cardiology",
        status="diagnostics",
        source="online",
    )
    target_day = date.today().isoformat()

    response = client.patch(
        f"/api/v1/registrar/batch/patients/{test_patient.id}/entries/{target_day}",
        headers=registrar_auth_headers,
        json={
            "entries": [
                {
                    "action": "create",
                    "specialty": "cardiology",
                    "service_code": service.service_code,
                }
            ]
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["updated_entries"][0]["status"] == "created"

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.number.asc(), OnlineQueueEntry.id.asc())
        .all()
    )
    assert [entry.id for entry in patient_entries] == [
        existing_entry.id,
        payload["updated_entries"][0]["id"],
    ]
    assert patient_entries[0].number == 8
    assert patient_entries[0].status == "diagnostics"
    assert patient_entries[1].number == 9
    assert patient_entries[1].source == "batch_update"
    assert patient_entries[1].service_codes == [normalize_service_code(service.service_code)]

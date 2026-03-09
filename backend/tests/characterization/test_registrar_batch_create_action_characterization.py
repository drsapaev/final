from __future__ import annotations

from datetime import date

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.batch_patient_service import (
    BatchPatientService,
    BatchUpdateRequest,
    EntryAction,
)


def _create_existing_entry(
    db_session,
    *,
    patient_id: int,
    number: int,
    status: str = "waiting",
    source: str = "desk",
) -> OnlineQueueEntry:
    queue = DailyQueue(
        day=date.today(),
        specialist_id=101,
        queue_tag="cardiology",
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
def test_registrar_batch_create_action_characterization_mounted_path_is_live_but_returns_400(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
):
    target_day = date.today().isoformat()
    before_count = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .count()
    )

    response = client.patch(
        f"/api/v1/registrar/batch/patients/{test_patient.id}/entries/{target_day}",
        headers=registrar_auth_headers,
        json={
            "entries": [
                {
                    "action": "create",
                    "specialty": "cardiology",
                    "service_code": "W2C-BATCH-CREATE",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "One or more operations failed"

    after_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .all()
    )
    assert len(after_entries) == before_count
    assert not any(entry.source == "batch_update" for entry in after_entries)


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_create_action_characterization_reports_queue_service_import_error(
    db_session,
    test_patient,
):
    service = BatchPatientService(db_session)

    result = service.batch_update(
        patient_id=test_patient.id,
        target_date=date.today(),
        request=BatchUpdateRequest(
            entries=[
                EntryAction(
                    action="create",
                    specialty="cardiology",
                    service_code="W2C-BATCH-CREATE",
                )
            ]
        ),
    )

    assert result.success is False
    assert len(result.updated_entries) == 1
    assert result.updated_entries[0].status == "error"
    assert "cannot import name 'QueueService'" in (result.updated_entries[0].error or "")


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_create_action_characterization_duplicate_scenario_still_creates_no_new_row(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
):
    existing_entry = _create_existing_entry(
        db_session,
        patient_id=test_patient.id,
        number=8,
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
                    "service_code": "W2C-BATCH-DUP",
                }
            ]
        },
    )

    assert response.status_code == 400
    assert response.json()["detail"] == "One or more operations failed"

    patient_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.id.asc())
        .all()
    )
    assert [entry.id for entry in patient_entries] == [existing_entry.id]
    assert patient_entries[0].number == existing_entry.number
    assert patient_entries[0].status == existing_entry.status
    assert patient_entries[0].source == existing_entry.source

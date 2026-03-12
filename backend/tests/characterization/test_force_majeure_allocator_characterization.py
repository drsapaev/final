from __future__ import annotations

from datetime import date, datetime, timedelta

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.force_majeure_service import ForceMajeureService

pytestmark = pytest.mark.postgres_pilot


def _create_daily_queue(
    db_session,
    *,
    specialist_id: int,
    queue_tag: str,
    day: date,
) -> DailyQueue:
    queue = DailyQueue(
        day=day,
        specialist_id=specialist_id,
        queue_tag=queue_tag,
        active=True,
    )
    db_session.add(queue)
    db_session.commit()
    db_session.refresh(queue)
    return queue


@pytest.mark.integration
@pytest.mark.queue
def test_force_majeure_allocator_characterization_transfer_creates_priority_row_with_new_number(
    client,
    db_session,
    registrar_auth_headers,
    test_doctor,
    test_patient,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.force_majeure_service.get_fcm_service",
        lambda: object(),
    )

    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        day=today,
    )
    tomorrow_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        day=tomorrow,
    )
    source_entry = OnlineQueueEntry(
        queue_id=today_queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=datetime.utcnow() - timedelta(hours=2),
    )
    existing_waiting = OnlineQueueEntry(
        queue_id=tomorrow_queue.id,
        number=4,
        patient_id=None,
        patient_name="Existing Waiting",
        phone="+998900001111",
        source="desk",
        status="waiting",
        queue_time=datetime.utcnow() - timedelta(minutes=30),
    )
    existing_cancelled = OnlineQueueEntry(
        queue_id=tomorrow_queue.id,
        number=99,
        patient_id=None,
        patient_name="Existing Cancelled",
        phone="+998900002222",
        source="desk",
        status="cancelled",
        queue_time=datetime.utcnow() - timedelta(minutes=10),
    )
    db_session.add_all([source_entry, existing_waiting, existing_cancelled])
    db_session.commit()
    db_session.refresh(source_entry)

    response = client.post(
        "/api/v1/force-majeure/transfer",
        headers=registrar_auth_headers,
        json={
            "specialist_id": test_doctor.id,
            "reason": "Characterization transfer",
            "entry_ids": [source_entry.id],
            "send_notifications": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["transferred"] == 1
    assert payload["failed"] == 0
    assert payload["details"][0]["new_number"] == 5

    transferred_entry = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == tomorrow_queue.id,
            OnlineQueueEntry.source == "force_majeure_transfer",
            OnlineQueueEntry.patient_id == test_patient.id,
        )
        .one()
    )
    assert transferred_entry.number == 5
    assert transferred_entry.status == "waiting"
    assert transferred_entry.priority == ForceMajeureService.TRANSFER_PRIORITY
    assert transferred_entry.queue_time is not None
    assert transferred_entry.queue_time != source_entry.queue_time
    assert transferred_entry.source == "force_majeure_transfer"

    db_session.refresh(source_entry)
    assert source_entry.status == "cancelled"
    assert "Форс-мажор" in (source_entry.incomplete_reason or "")


@pytest.mark.integration
@pytest.mark.queue
def test_force_majeure_allocator_characterization_transfer_does_not_gate_duplicates_on_tomorrow_queue(
    client,
    db_session,
    registrar_auth_headers,
    test_doctor,
    test_patient,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.force_majeure_service.get_fcm_service",
        lambda: object(),
    )

    today = date.today()
    tomorrow = today + timedelta(days=1)
    today_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        day=today,
    )
    tomorrow_queue = _create_daily_queue(
        db_session,
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        day=tomorrow,
    )
    source_entry = OnlineQueueEntry(
        queue_id=today_queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="called",
        queue_time=datetime.utcnow() - timedelta(hours=1),
    )
    existing_tomorrow_entry = OnlineQueueEntry(
        queue_id=tomorrow_queue.id,
        number=4,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=datetime.utcnow() - timedelta(minutes=20),
    )
    db_session.add_all([source_entry, existing_tomorrow_entry])
    db_session.commit()
    db_session.refresh(source_entry)

    response = client.post(
        "/api/v1/force-majeure/transfer",
        headers=registrar_auth_headers,
        json={
            "specialist_id": test_doctor.id,
            "reason": "Duplicate characterization transfer",
            "entry_ids": [source_entry.id],
            "send_notifications": False,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["transferred"] == 1
    assert payload["failed"] == 0

    active_tomorrow_entries = (
        db_session.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.queue_id == tomorrow_queue.id,
            OnlineQueueEntry.patient_id == test_patient.id,
            OnlineQueueEntry.status == "waiting",
        )
        .order_by(OnlineQueueEntry.number.asc())
        .all()
    )
    assert len(active_tomorrow_entries) == 2
    assert [entry.number for entry in active_tomorrow_entries] == [4, 5]
    assert {entry.source for entry in active_tomorrow_entries} == {
        "online",
        "force_majeure_transfer",
    }

    transferred_entry = next(
        entry
        for entry in active_tomorrow_entries
        if entry.source == "force_majeure_transfer"
    )
    assert transferred_entry.priority == ForceMajeureService.TRANSFER_PRIORITY
    assert transferred_entry.queue_time is not None

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.services.force_majeure_service import ForceMajeureService
from app.services.queue_service import QueueBusinessService, queue_service

pytestmark = pytest.mark.postgres_pilot


def _create_daily_queue_and_token(db_session, test_doctor, token_value: str) -> tuple[DailyQueue, QueueToken]:
    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.commit()
    db_session.refresh(daily_queue)

    local_now = datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
    token = QueueToken(
        token=token_value,
        day=date.today(),
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=local_now + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return daily_queue, token


@pytest.mark.integration
@pytest.mark.queue
def test_online_join_characterization_service_path_assigns_waiting_online_entry(
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue, token = _create_daily_queue_and_token(
        db_session,
        test_doctor,
        token_value="characterization-online-join",
    )

    join_result = queue_service.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="Characterization Patient",
        phone="+998901111111",
        source="online",
    )

    assert join_result["duplicate"] is False
    assert join_result["entry"].number >= 1

    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .one()
    )
    assert entry.number == join_result["entry"].number
    assert entry.source == "online"
    assert entry.status == "waiting"
    assert entry.queue_time is not None


@pytest.mark.integration
@pytest.mark.queue
def test_qr_session_join_characterization_assigns_waiting_entry(
    client,
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue, token = _create_daily_queue_and_token(
        db_session,
        test_doctor,
        token_value="characterization-qr-session",
    )

    start_response = client.post("/api/v1/queue/join/start", json={"token": token.token})
    assert start_response.status_code == 200
    session_token = start_response.json()["session_token"]

    complete_response = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "QR Session Patient",
            "phone": "+998902222222",
        },
    )
    assert complete_response.status_code == 200
    payload = complete_response.json()
    assert payload["success"] is True
    assert payload["queue_number"] >= 1

    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .one()
    )
    assert entry.number == payload["queue_number"]
    assert entry.source == "online"
    assert entry.status == "waiting"
    assert entry.queue_time is not None


@pytest.mark.integration
@pytest.mark.queue
def test_telegram_join_characterization_reuses_existing_waiting_entry(
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue, token = _create_daily_queue_and_token(
        db_session,
        test_doctor,
        token_value="characterization-telegram-join",
    )

    first = queue_service.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="Telegram Patient",
        telegram_id=123456789,
        source="online",
    )
    second = queue_service.join_queue_with_token(
        db_session,
        token_str=token.token,
        patient_name="Telegram Patient",
        telegram_id=123456789,
        source="online",
    )

    assert first["duplicate"] is False
    assert second["duplicate"] is True
    assert first["entry"].id == second["entry"].id
    assert first["entry"].number == second["entry"].number
    assert first["entry"].queue_time == second["entry"].queue_time
    assert first["entry"].status == "waiting"
    assert first["entry"].source == "online"

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 1


@pytest.mark.integration
@pytest.mark.queue
def test_registrar_batch_characterization_preserves_desk_source_and_waiting_status(
    client,
    db_session,
    registrar_auth_headers,
    test_patient,
    cardio_user,
    test_doctor,
    test_service,
):
    response = client.post(
        "/api/v1/registrar-integration/queue/entries/batch",
        headers=registrar_auth_headers,
        json={
            "patient_id": test_patient.id,
            "source": "desk",
            "services": [
                {
                    "specialist_id": cardio_user.id,
                    "service_id": test_service.id,
                    "quantity": 1,
                }
            ],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert len(payload["entries"]) == 1
    assert payload["entries"][0]["number"] >= 1
    assert payload["entries"][0]["queue_time"]

    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.patient_id == test_patient.id)
        .order_by(OnlineQueueEntry.id.desc())
        .first()
    )
    assert entry is not None
    assert entry.number == payload["entries"][0]["number"]
    assert entry.source == "desk"
    assert entry.status == "waiting"
    assert entry.queue_time is not None


@pytest.mark.integration
@pytest.mark.queue
def test_force_majeure_transfer_characterization_preserves_current_allocator_behavior(
    db_session,
    test_doctor,
    test_patient,
    monkeypatch,
):
    monkeypatch.setattr(
        "app.services.force_majeure_service.get_fcm_service",
        lambda: object(),
    )

    today_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    tomorrow_queue = DailyQueue(
        day=date.today() + timedelta(days=1),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add_all([today_queue, tomorrow_queue])
    db_session.commit()
    db_session.refresh(today_queue)
    db_session.refresh(tomorrow_queue)

    source_entry = OnlineQueueEntry(
        queue_id=today_queue.id,
        number=1,
        patient_id=test_patient.id,
        patient_name=test_patient.short_name(),
        phone=test_patient.phone,
        source="online",
        status="waiting",
        queue_time=datetime.utcnow(),
    )
    existing_waiting = OnlineQueueEntry(
        queue_id=tomorrow_queue.id,
        number=4,
        patient_id=None,
        patient_name="Existing Waiting",
        source="desk",
        status="waiting",
        queue_time=datetime.utcnow(),
    )
    existing_cancelled = OnlineQueueEntry(
        queue_id=tomorrow_queue.id,
        number=99,
        patient_id=None,
        patient_name="Existing Cancelled",
        source="desk",
        status="cancelled",
        queue_time=datetime.utcnow(),
    )
    db_session.add_all([source_entry, existing_waiting, existing_cancelled])
    db_session.commit()
    db_session.refresh(source_entry)

    service = ForceMajeureService(db_session)
    result = service.transfer_entries_to_tomorrow(
        entries=[source_entry],
        specialist_id=test_doctor.id,
        reason="Characterization transfer",
        performed_by_id=1,
        send_notifications=False,
    )

    assert result["success"] is True
    assert result["transferred"] == 1

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

    db_session.refresh(source_entry)
    assert source_entry.status == "cancelled"

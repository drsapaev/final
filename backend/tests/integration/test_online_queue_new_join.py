from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.services.queue_service import QueueBusinessService


def _make_daily_queue_and_token(db_session, test_doctor, token_value: str):
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
def test_online_queue_new_join_success_preserves_behavior(
    client,
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue, token = _make_daily_queue_and_token(
        db_session,
        test_doctor,
        token_value="online-queue-new-success",
    )

    response = client.post(
        "/api/v1/online-queue/join",
        json={
            "token": token.token,
            "patient_name": "Online Queue Patient",
            "phone": "+998906060606",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["duplicate"] is False
    assert payload["number"] >= 1

    entry = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .one()
    )
    assert entry.number == payload["number"]
    assert entry.source == "online"
    assert entry.status == "waiting"
    assert entry.queue_time is not None


@pytest.mark.integration
@pytest.mark.queue
def test_online_queue_new_join_duplicate_reuses_existing_entry(
    client,
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    daily_queue, token = _make_daily_queue_and_token(
        db_session,
        test_doctor,
        token_value="online-queue-new-duplicate",
    )

    first = client.post(
        "/api/v1/online-queue/join",
        json={
            "token": token.token,
            "patient_name": "Duplicate Patient",
            "phone": "+998907070707",
        },
    )
    second = client.post(
        "/api/v1/online-queue/join",
        json={
            "token": token.token,
            "patient_name": "Duplicate Patient",
            "phone": "+998907070707",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    first_payload = first.json()
    second_payload = second.json()
    assert first_payload["success"] is True
    assert second_payload["success"] is True
    assert first_payload["number"] == second_payload["number"]
    assert second_payload["duplicate"] is True

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 1

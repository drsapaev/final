"""
Integration tests for QR queue join flow (start/complete).
Focus: public endpoints and duplicate protection.
"""

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.services.queue_service import QueueBusinessService


@pytest.mark.queue
def test_qr_join_flow_success(client, db_session, test_doctor, monkeypatch):
    # Ensure time restrictions never block the test
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    # Arrange: daily queue + active token
    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.commit()

    token_value = "test-qr-token"
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

    # Act: start join session
    start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    # Act: complete join session
    complete_resp = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "Test Patient",
            "phone": "+998901112233",
        },
    )
    assert complete_resp.status_code == 200
    payload = complete_resp.json()

    # Assert
    assert payload["success"] is True
    assert payload["queue_number"] >= 1


@pytest.mark.queue
def test_qr_join_duplicate_is_not_recreated(client, db_session, test_doctor, monkeypatch):
    # Ensure time restrictions never block the test
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))

    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.commit()

    token_value = "test-qr-token-dup"
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

    # First join
    start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp.status_code == 200
    session_token = start_resp.json()["session_token"]

    complete_resp = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "Test Patient",
            "phone": "+998901112233",
        },
    )
    assert complete_resp.status_code == 200
    first_number = complete_resp.json()["queue_number"]

    # Second join with same phone (should reuse existing entry)
    start_resp_2 = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp_2.status_code == 200
    session_token_2 = start_resp_2.json()["session_token"]

    complete_resp_2 = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token_2,
            "patient_name": "Test Patient",
            "phone": "+998901112233",
        },
    )
    assert complete_resp_2.status_code == 200
    second_number = complete_resp_2.json()["queue_number"]

    assert first_number == second_number

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.queue_id == daily_queue.id)
        .all()
    )
    assert len(entries) == 1

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.services.queue_service import QueueBusinessService

pytestmark = pytest.mark.postgres_pilot


def _create_daily_queue_and_token(db_session, test_doctor, token_value: str) -> QueueToken:
    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.commit()

    token = QueueToken(
        token=token_value,
        day=date.today(),
        specialist_id=test_doctor.id,
        department="cardiology",
        expires_at=datetime.now(ZoneInfo("Asia/Tashkent")).replace(tzinfo=None)
        + timedelta(hours=2),
        active=True,
    )
    db_session.add(token)
    db_session.commit()
    db_session.refresh(token)
    return token


@pytest.mark.integration
@pytest.mark.queue
def test_qr_direct_sql_concurrency_same_session_replay_fails_without_new_row(
    client,
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    token = _create_daily_queue_and_token(db_session, test_doctor, "w2c-qr-replay")

    start_response = client.post("/api/v1/queue/join/start", json={"token": token.token})
    assert start_response.status_code == 200
    session_token = start_response.json()["session_token"]

    complete_response = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "QR Replay Patient",
            "phone": "+998904040404",
        },
    )
    replay_response = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": session_token,
            "patient_name": "QR Replay Patient",
            "phone": "+998904040404",
        },
    )

    assert complete_response.status_code == 200
    assert replay_response.status_code == 400
    assert "Сессия не найдена или истекла" in replay_response.json()["detail"]

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.phone == "+998904040404")
        .all()
    )
    assert len(entries) == 1


@pytest.mark.integration
@pytest.mark.queue
def test_qr_direct_sql_concurrency_two_pending_sessions_reuse_single_entry(
    client,
    db_session,
    test_doctor,
    monkeypatch,
):
    monkeypatch.setattr(QueueBusinessService, "ONLINE_QUEUE_START_TIME", time(0, 0))
    token = _create_daily_queue_and_token(db_session, test_doctor, "w2c-qr-two-pending")

    start_response_1 = client.post("/api/v1/queue/join/start", json={"token": token.token})
    start_response_2 = client.post("/api/v1/queue/join/start", json={"token": token.token})
    assert start_response_1.status_code == 200
    assert start_response_2.status_code == 200

    complete_response_1 = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": start_response_1.json()["session_token"],
            "patient_name": "QR Pending Patient",
            "phone": "+998905050505",
        },
    )
    complete_response_2 = client.post(
        "/api/v1/queue/join/complete",
        json={
            "session_token": start_response_2.json()["session_token"],
            "patient_name": "QR Pending Patient",
            "phone": "+998905050505",
        },
    )

    assert complete_response_1.status_code == 200
    assert complete_response_2.status_code == 200
    assert complete_response_1.json()["queue_number"] == complete_response_2.json()["queue_number"]

    entries = (
        db_session.query(OnlineQueueEntry)
        .filter(OnlineQueueEntry.phone == "+998905050505")
        .all()
    )
    assert len(entries) == 1

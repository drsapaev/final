"""
E2E integration tests for queue time window (07:00) and WebSocket queue events.
"""

import json
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

import app.services.qr_queue_service as qr_queue_service
import app.services.queue_service as queue_service_module
from app.models.online_queue import DailyQueue, QueueToken
from app.services.display_websocket import get_display_manager


class DummyWebSocket:
    def __init__(self) -> None:
        self.sent = []

    async def send_text(self, text: str) -> None:
        self.sent.append(text)


def _freeze_datetime(monkeypatch, frozen_dt: datetime) -> None:
    class FixedDateTime(datetime):
        @classmethod
        def now(cls, tz=None):  # type: ignore[override]
            if tz is not None:
                return frozen_dt.replace(tzinfo=tz)
            return frozen_dt

        @classmethod
        def utcnow(cls):  # type: ignore[override]
            return frozen_dt

    monkeypatch.setattr(qr_queue_service, "datetime", FixedDateTime)
    monkeypatch.setattr(queue_service_module, "datetime", FixedDateTime)


def _create_queue_and_token(db_session, test_doctor, token_value: str) -> str:
    daily_queue = DailyQueue(
        day=date.today(),
        specialist_id=test_doctor.id,
        queue_tag="cardiology_common",
        active=True,
    )
    db_session.add(daily_queue)
    db_session.commit()

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

    return token_value


@pytest.mark.e2e
def test_queue_join_blocked_before_start_time(
    client, db_session, test_doctor, monkeypatch
):
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)
    _freeze_datetime(monkeypatch, datetime(2026, 1, 1, 6, 30))

    token_value = _create_queue_and_token(db_session, test_doctor, "qr-time-early")

    start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp.status_code == 400
    assert "Онлайн-запись откроется" in start_resp.json()["detail"]


@pytest.mark.e2e
def test_queue_join_allows_after_start_time(
    client, db_session, test_doctor, monkeypatch
):
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)
    _freeze_datetime(monkeypatch, datetime(2026, 1, 1, 7, 5))

    token_value = _create_queue_and_token(db_session, test_doctor, "qr-time-open")

    start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
    assert start_resp.status_code == 200
    assert start_resp.json()["session_token"]


@pytest.mark.e2e
def test_queue_created_event_broadcasted(
    client, db_session, test_doctor, monkeypatch
):
    monkeypatch.delenv("DISABLE_QUEUE_TIME_RESTRICTIONS", raising=False)
    _freeze_datetime(monkeypatch, datetime(2026, 1, 1, 7, 5))

    token_value = _create_queue_and_token(db_session, test_doctor, "qr-time-ws")

    manager = get_display_manager()
    prev_connections = manager.connections
    prev_states = manager.board_states

    ws = DummyWebSocket()
    manager.connections = {"test-board": {ws}}
    manager.board_states = {}

    try:
        start_resp = client.post("/api/v1/queue/join/start", json={"token": token_value})
        assert start_resp.status_code == 200
        session_token = start_resp.json()["session_token"]

        complete_resp = client.post(
            "/api/v1/queue/join/complete",
            json={
                "session_token": session_token,
                "patient_name": "Queue WS Test",
                "phone": "+998900000001",
            },
        )
        assert complete_resp.status_code == 200
        assert ws.sent, "Expected queue.created event to be broadcasted"

        payload = json.loads(ws.sent[-1])
        assert payload["type"] == "queue_update"
        assert payload["event_type"] == "queue.created"
        assert payload["data"]["source"] == "online"
    finally:
        manager.connections = prev_connections
        manager.board_states = prev_states

"""Synthetic ASGI checks for the doctor call and its manual queue counterpart."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import update

from app.api.v1.endpoints.doctor_integration import _queue_ops
from app.crud.clinic import clinic_today
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services import display_websocket
from app.services.qr_queue_service import QRQueueService

pytestmark = pytest.mark.integration


def _doctor(client, db, user):
    doctor = Doctor(
        user_id=user.id, specialty="dermatology", active=True, cabinet="101"
    )
    db.add(doctor)
    db.flush()
    response = client.post(
        "/api/v1/authentication/login",
        json={"username": user.username, "password": "doctor123"},
    )
    assert response.status_code == 200
    return doctor, {"Authorization": f"Bearer {response.json()['access_token']}"}


def _queue(db, doctor, queue_tag, *, active=True, day=None):
    queue = DailyQueue(
        day=day if day is not None else clinic_today(db),
        specialist_id=doctor.id,
        queue_tag=queue_tag,
        active=active,
    )
    db.add(queue)
    db.flush()
    return queue


def _entry(db, queue, number, *, priority=0, queue_time=None, created_at=None):
    entry = OnlineQueueEntry(
        queue_id=queue.id,
        number=number,
        patient_name="SYNTHETIC-QUEUE-FLOW",
        source="desk",
        status="waiting",
        priority=priority,
        queue_time=queue_time,
        created_at=created_at or datetime.now(UTC),
    )
    db.add(entry)
    db.flush()
    return entry


@pytest.mark.parametrize("priority", [0, 1])
def test_doctor_next_matches_qr_call_order_across_queues(
    client,
    db_session,
    test_doctor_user,
    priority,
):
    doctor, headers = _doctor(client, db_session, test_doctor_user)
    clinic_day = clinic_today(db_session)
    older_queue_id = _queue(db_session, doctor, "dermatology", day=clinic_day)
    newer_queue_id = _queue(db_session, doctor, "dermatology_procedure", day=clinic_day)
    inactive = _queue(
        db_session, doctor, "dermatology_closed", active=False, day=clinic_day
    )
    base = datetime.now(UTC) - timedelta(hours=1)
    _entry(db_session, older_queue_id, 1, queue_time=base + timedelta(minutes=15))
    _entry(db_session, inactive, 1, priority=2, queue_time=base)
    next_entry = _entry(
        db_session,
        newer_queue_id,
        9,
        priority=priority,
        created_at=base,
    )
    _entry(
        db_session,
        newer_queue_id,
        1,
        priority=priority,
        queue_time=base,
    )
    response = client.get("/api/v1/doctor/dermatology/queue/today", headers=headers)
    assert response.status_code == 200
    preview = response.json()
    assert preview["next_call_entry_id"] == next_entry.id
    assert preview["can_call_next"] is True

    manual = QRQueueService(db_session).call_next_patient(
        doctor.id,
        test_doctor_user.id,
        clinic_day,
    )
    assert manual["patient"]["id"] == next_entry.id


@pytest.mark.parametrize(
    ("competitor_priority", "earlier", "restored_wins"),
    [(0, True, True), (2, False, False), (1, True, False)],
)
def test_priority_return_respects_ranking_on_manual_and_doctor_paths(
    client, db_session, test_doctor_user, monkeypatch,
    competitor_priority, earlier, restored_wins,
):
    doctor, headers = _doctor(client, db_session, test_doctor_user)
    clinic_day = clinic_today(db_session)
    queue_a = _queue(db_session, doctor, "dermatology", day=clinic_day)
    queue_b = _queue(db_session, doctor, "dermatology_procedure", day=clinic_day)
    enqueue = datetime.now(UTC) - timedelta(hours=1)
    # #4281 verifies the restore mutation itself. Seed its committed
    # result here: waiting at priority 1, original enqueue time retained.
    returned = _entry(db_session, queue_a, 9, priority=1, queue_time=enqueue)
    competitor = _entry(
        db_session, queue_b, 1, priority=competitor_priority,
        queue_time=enqueue + timedelta(minutes=-10 if earlier else 10),
    )
    expected = returned if restored_wins else competitor
    other = competitor if restored_wins else returned

    manual = QRQueueService(db_session).call_next_patient(
        doctor.id, test_doctor_user.id, clinic_day,
    )
    assert manual["patient"]["id"] == expected.id
    # Restore the independent starting state before exercising exactly
    # the GET and POST endpoints used by the browser's completion action.
    db_session.refresh(expected)
    expected.status = "waiting"
    expected.called_at = None
    expected.called_by_user_id = None
    db_session.commit()
    def offline_board():
        raise RuntimeError("synthetic offline board")

    monkeypatch.setattr(display_websocket, "get_display_manager", offline_board)
    preview = client.get("/api/v1/doctor/dermatology/queue/today", headers=headers)
    assert preview.status_code == 200
    assert preview.json()["next_call_entry_id"] == expected.id
    ack = client.post(f"/api/v1/doctor/queue/{expected.id}/call", headers=headers)
    assert ack.status_code == 200
    assert ack.json()["entry"]["id"] == expected.id
    assert ack.json()["display_delivery"] == "unconfirmed"
    db_session.refresh(other)
    assert other.status == "waiting"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (
            {"board-a": "delivered_local", "board-b": "published_only"},
            "delivered_local",
        ),
        ({"board-a": "published_only", "board-b": "published_only"}, "published_only"),
        ({"board-a": "published_only", "board-b": "failed"}, "partial"),
        ({}, "unconfirmed"),
        (RuntimeError("synthetic transport failure"), "unconfirmed"),
    ],
)
def test_doctor_call_announces_on_asgi_loop_and_keeps_commit(
    client,
    db_session,
    test_doctor_user,
    monkeypatch,
    outcome,
    expected,
):
    doctor, headers = _doctor(client, db_session, test_doctor_user)
    queue = _queue(db_session, doctor, "dermatology")
    entry = _entry(db_session, queue, 12)
    manager = display_websocket.DisplayWebSocketManager()
    monkeypatch.setattr(
        manager, "_resolve_untargeted_board_ids", lambda: ["board-a", "board-b"]
    )
    monkeypatch.setattr(manager, "_resolve_name_format", lambda board_ids: "none")
    send = AsyncMock(
        side_effect=outcome if isinstance(outcome, Exception) else None,
        return_value=outcome if isinstance(outcome, dict) else None,
    )
    monkeypatch.setattr(manager, "broadcast_patient_call_data", send)
    monkeypatch.setattr(display_websocket, "get_display_manager", lambda: manager)

    url = f"/api/v1/doctor/queue/{entry.id}/call"
    response = client.post(url, headers=headers)
    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    assert payload["display_delivery"] == expected
    assert "board-a" not in response.text
    db_session.refresh(entry)
    assert entry.status == "called"
    assert entry.called_by_user_id == test_doctor_user.id
    send.assert_awaited_once()
    message = send.await_args.args[0]
    assert message["type"] == "patient_call"
    assert message["data"]["queue_number"] == 12
    assert message["data"]["cabinet"] == "101"
    assert "SYNTHETIC-QUEUE-FLOW" not in str(message)
    assert send.await_args.kwargs["board_ids"] == ["board-a", "board-b"]

    repeated = client.post(url, headers=headers)
    assert repeated.status_code == 400
    send.assert_awaited_once()


def test_doctor_call_rejects_inactive_queue_without_announcement(
    client,
    db_session,
    test_doctor_user,
    monkeypatch,
):
    doctor, headers = _doctor(client, db_session, test_doctor_user)
    queue = _queue(db_session, doctor, "dermatology_closed", active=False)
    entry = _entry(db_session, queue, 3)
    get_manager = AsyncMock()
    monkeypatch.setattr(display_websocket, "get_display_manager", get_manager)
    response = client.post(f"/api/v1/doctor/queue/{entry.id}/call", headers=headers)
    assert response.status_code == 409
    db_session.refresh(entry)
    assert entry.status == "waiting"
    get_manager.assert_not_called()


def test_doctor_call_loses_a_claim_after_reading_waiting(
    client,
    db_session,
    test_doctor_user,
    monkeypatch,
):
    doctor, headers = _doctor(client, db_session, test_doctor_user)
    queue = _queue(db_session, doctor, "dermatology")
    entry = _entry(db_session, queue, 8)
    db_session.commit()
    entry_id = entry.id
    original = _queue_ops._doctor_queue_available_actions

    def after_waiting_read(selected):
        actions = original(selected)
        # Force the exact interleaving: an earlier read saw waiting, but
        # another change has already made the row called at write time.
        db_session.execute(
            update(OnlineQueueEntry)
            .where(OnlineQueueEntry.id == entry_id)
            .values(status="called")
            .execution_options(synchronize_session=False)
        )
        db_session.commit()
        return actions

    monkeypatch.setattr(
        _queue_ops, "_doctor_queue_available_actions", after_waiting_read
    )
    get_manager = AsyncMock()
    monkeypatch.setattr(display_websocket, "get_display_manager", get_manager)
    response = client.post(f"/api/v1/doctor/queue/{entry_id}/call", headers=headers)
    assert response.status_code == 409
    get_manager.assert_not_called()


def test_stalled_board_does_not_delay_healthy_board_or_repeat_call(
    client, db_session, test_doctor_user, monkeypatch
):
    import asyncio
    import json

    doctor, headers = _doctor(client, db_session, test_doctor_user)
    entry = _entry(db_session, _queue(db_session, doctor, "dermatology"), 17)
    trace = []
    messages = []

    class Stalled:
        async def send_text(self, _payload):
            trace.append("stalled")
            try:
                await asyncio.sleep(0.8)
            except asyncio.CancelledError:
                trace.append("cancelled")
                raise

    class Healthy:
        async def send_text(self, payload):
            trace.append("healthy")
            messages.append(json.loads(payload))

    bridge = AsyncMock()
    bridge.subscribe.return_value = True
    bridge.publish.return_value = False  # no other worker confirmed
    manager = display_websocket.DisplayWebSocketManager(pubsub=bridge)
    stalled, healthy = Stalled(), Healthy()
    manager.connections = {"stalled-board": {stalled}, "healthy-board": {healthy}}
    monkeypatch.setattr(
        manager,
        "_resolve_untargeted_board_ids",
        lambda: ["stalled-board", "healthy-board"],
    )
    monkeypatch.setattr(manager, "_resolve_name_format", lambda _ids: "none")
    monkeypatch.setattr(display_websocket, "get_display_manager", lambda: manager)
    monkeypatch.setattr(
        display_websocket, "DISPLAY_SOCKET_SEND_TIMEOUT_SECONDS", 0.08, raising=False
    )
    monkeypatch.setattr(
        display_websocket, "DISPLAY_CALL_TARGET_TIMEOUT_SECONDS", 0.3, raising=False
    )

    url = f"/api/v1/doctor/queue/{entry.id}/call"
    response = client.post(url, headers=headers)
    assert response.status_code == 200
    assert response.json()["success"] is True
    assert response.json()["display_delivery"] == "partial"
    assert not {"stalled-board", "healthy-board"} & set(response.text.split('"'))
    assert trace == ["stalled", "healthy", "cancelled"]
    assert len(messages) == 1
    assert messages[0]["data"]["queue_number"] == entry.number
    assert "SYNTHETIC-QUEUE-FLOW" not in str(messages)
    db_session.refresh(entry)
    assert entry.status == "called"
    called_at = entry.called_at

    assert client.post(url, headers=headers).status_code == 400
    db_session.refresh(entry)
    assert entry.called_at == called_at
    assert len(messages) == 1

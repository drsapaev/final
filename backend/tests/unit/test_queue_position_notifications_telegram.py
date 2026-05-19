from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services import notifications as notifications_module
from app.services.queue_position_notifications import QueuePositionNotificationService


def _queue_entry(*, patient_id: int, status: str = "waiting") -> SimpleNamespace:
    return SimpleNamespace(
        id=9901,
        patient_id=patient_id,
        patient_name="Queue Patient",
        number=8,
        telegram_id=None,
        status=status,
    )


@pytest.mark.asyncio
async def test_patient_called_notification_routes_safe_telegram_event(
    db_session,
    test_patient,
    monkeypatch,
):
    test_patient.user_id = None
    db_session.commit()
    telegram_mock = AsyncMock(return_value=True)
    push_mock = AsyncMock(return_value=False)
    monkeypatch.setattr(
        notifications_module.notification_sender_service,
        "send_patient_telegram_event_notification",
        telegram_mock,
    )
    monkeypatch.setattr(
        notifications_module.notification_sender_service,
        "send_push",
        push_mock,
    )

    result = await QueuePositionNotificationService(db_session).notify_patient_called(
        entry=_queue_entry(patient_id=test_patient.id),
        cabinet_number="205",
    )

    assert result["success"] is True
    assert result["sent"] is True
    assert result["telegram_sent"] is True
    push_mock.assert_not_awaited()
    telegram_mock.assert_awaited_once()
    kwargs = telegram_mock.await_args.kwargs
    assert kwargs["db"] is db_session
    assert kwargs["patient_id"] == test_patient.id
    assert kwargs["event_type"] == "PatientCalled"
    assert kwargs["metadata"] == {
        "queue_number": "8",
        "cabinet": "205",
        "status": "called",
    }
    assert "entry_id" not in kwargs["metadata"]


@pytest.mark.asyncio
async def test_position_update_notification_routes_queue_status_to_telegram(
    db_session,
    test_patient,
    monkeypatch,
):
    test_patient.user_id = None
    db_session.commit()
    telegram_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(
        notifications_module.notification_sender_service,
        "send_patient_telegram_event_notification",
        telegram_mock,
    )

    result = await QueuePositionNotificationService(db_session).notify_position_update(
        entry=_queue_entry(patient_id=test_patient.id),
        people_ahead=1,
    )

    assert result["success"] is True
    assert result["sent"] is True
    assert result["telegram_sent"] is True
    telegram_mock.assert_awaited_once()
    kwargs = telegram_mock.await_args.kwargs
    assert kwargs["event_type"] == "QueueStatusChanged"
    assert kwargs["metadata"] == {
        "queue_number": "8",
        "cabinet": "",
        "status": "waiting",
    }
    assert "entry_id" not in kwargs["metadata"]
    assert "patient_id" not in kwargs["metadata"]

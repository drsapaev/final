from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import mobile_api


@pytest.mark.asyncio
async def test_mobile_notifications_list_uses_owned_rows_and_model_fields(
    monkeypatch,
):
    notification = SimpleNamespace(
        id=10,
        subject="Visit reminder",
        content="Tomorrow at 10:00",
        notification_type="appointment",
        notification_metadata={"appointment_id": 42},
        created_at="2026-05-31T10:00:00",
    )
    calls = {}

    def fail_stale_crud(*_args, **_kwargs):
        raise AssertionError("stale user_id NotificationHistory helper used")

    def fake_rows(_db, *, user_id, patient_id, limit, offset):
        calls.update(
            {
                "user_id": user_id,
                "patient_id": patient_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return [notification]

    monkeypatch.setattr(
        mobile_api.crud_notification,
        "get_user_notifications",
        fail_stale_crud,
    )
    monkeypatch.setattr(
        mobile_api,
        "get_patient_by_user_id",
        lambda _db, user_id: SimpleNamespace(id=9, user_id=user_id),
    )
    monkeypatch.setattr(mobile_api, "_get_mobile_notification_rows", fake_rows)

    response = await mobile_api.get_mobile_notifications(
        current_user=SimpleNamespace(id=55),
        db=object(),
        limit=7,
        offset=2,
    )

    assert calls == {"user_id": 55, "patient_id": 9, "limit": 7, "offset": 2}
    assert response == [
        {
            "id": 10,
            "title": "Visit reminder",
            "message": "Tomorrow at 10:00",
            "type": "appointment",
            "data": {"appointment_id": 42},
            "sent_at": "2026-05-31T10:00:00",
            "read": False,
        }
    ]


@pytest.mark.asyncio
async def test_mobile_notification_read_accepts_owned_user_notification(monkeypatch):
    notification = SimpleNamespace(
        id=10,
        recipient_type="user",
        recipient_id=123,
        read=False,
    )
    calls = {"marked": False}

    monkeypatch.setattr(
        mobile_api.crud_notification,
        "get_notification",
        lambda _db, notification_id: notification,
        raising=False,
    )

    class FakeMobileApiService:
        def __init__(self, _db):
            pass

        def mark_notification_as_read(self, *, notification):
            calls["marked"] = True
            notification.read = True
            return True

    monkeypatch.setattr(mobile_api, "MobileApiService", FakeMobileApiService)

    response = await mobile_api.mark_notification_read(
        notification_id=10,
        current_user=SimpleNamespace(id=123),
        db=object(),
    )

    assert response["message"]
    assert calls["marked"] is True
    assert notification.read is True


@pytest.mark.asyncio
async def test_mobile_notification_read_rejects_other_patient_notification(
    monkeypatch,
):
    notification = SimpleNamespace(
        id=10,
        recipient_type="patient",
        recipient_id=999,
        read=False,
    )
    calls = {"marked": False}

    monkeypatch.setattr(
        mobile_api.crud_notification,
        "get_notification",
        lambda _db, notification_id: notification,
        raising=False,
    )
    monkeypatch.setattr(
        mobile_api,
        "get_patient_by_user_id",
        lambda _db, user_id: SimpleNamespace(id=123, user_id=user_id),
    )

    class FakeMobileApiService:
        def __init__(self, _db):
            pass

        def mark_notification_as_read(self, *, notification):
            calls["marked"] = True
            return True

    monkeypatch.setattr(mobile_api, "MobileApiService", FakeMobileApiService)

    with pytest.raises(HTTPException) as exc_info:
        await mobile_api.mark_notification_read(
            notification_id=10,
            current_user=SimpleNamespace(id=77),
            db=object(),
        )

    assert exc_info.value.status_code == 404
    assert calls["marked"] is False

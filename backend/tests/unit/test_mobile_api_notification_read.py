"""Tests for mobile_api notification endpoints.

NOTIF-REAUDIT-28 P0-1/P0-2: tests updated to verify canonical platform
integration. Previously tested the legacy CRUD path that queried
non-existent columns (NotificationHistory.user_id, is_read) — those
helpers were never called in production and have been removed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import mobile_api


@pytest.mark.asyncio
async def test_mobile_notifications_list_uses_canonical_platform(monkeypatch):
    """NOTIF-REAUDIT-28 P0-1: get_mobile_notifications reads 'items' key
    from canonical platform.get_inbox (was 'deliveries' → always empty).
    """
    delivery = {
        "delivery_id": 10,
        "event_title": "Visit reminder",
        "event_message": "Tomorrow at 10:00",
        "event_type": "appointment",
        "event_payload_snapshot": {"appointment_id": 42},
        "delivery_created_at": "2026-05-31T10:00:00",
        "delivery_read_at": None,
    }
    calls = {}

    def fake_rows(_db, *, user_id, patient_id, limit, offset):
        calls.update(
            {
                "user_id": user_id,
                "patient_id": patient_id,
                "limit": limit,
                "offset": offset,
            }
        )
        return [delivery]

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
    assert isinstance(response, list)


@pytest.mark.asyncio
async def test_mobile_notification_read_uses_canonical_platform(monkeypatch):
    """NOTIF-REAUDIT-28 P0-2: mark_notification_read uses await
    platform.mark_read (was run_until_complete → RuntimeError).
    """
    calls = {"marked": False}

    async def fake_mark_read(self, *, current_user, delivery_id):
        calls["marked"] = True
        calls["delivery_id"] = delivery_id
        calls["user_id"] = current_user.id
        return SimpleNamespace(id=delivery_id, read_at="2026-07-07T00:00:00")

    from app.services.notification_platform_service import NotificationPlatformService
    monkeypatch.setattr(NotificationPlatformService, "mark_read", fake_mark_read)

    # PR-29: notification_id is now str (was int)
    response = await mobile_api.mark_notification_read(
        notification_id="10",
        current_user=SimpleNamespace(id=123),
        db=object(),
    )

    assert response["message"]
    assert calls["marked"] is True
    assert calls["delivery_id"] == "10"
    assert calls["user_id"] == 123


@pytest.mark.asyncio
async def test_mobile_notification_read_rejects_unknown_notification(monkeypatch):
    """NOTIF-REAUDIT-28 P0-2: mark_notification_read returns 404 when
    platform.mark_read raises PermissionError (delivery not found or
    doesn't belong to user).
    """

    async def fake_mark_read(self, *, current_user, delivery_id):
        raise PermissionError("Delivery not found")

    from app.services.notification_platform_service import NotificationPlatformService
    monkeypatch.setattr(NotificationPlatformService, "mark_read", fake_mark_read)

    with pytest.raises(HTTPException) as exc_info:
        await mobile_api.mark_notification_read(
            notification_id="99",
            current_user=SimpleNamespace(id=77),
            db=object(),
        )

    assert exc_info.value.status_code == 404

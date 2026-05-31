from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.v1.endpoints import mobile_api


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

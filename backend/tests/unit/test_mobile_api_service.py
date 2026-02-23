from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.mobile_api_service import MobileApiService


@pytest.mark.unit
class TestMobileApiService:
    def test_update_user_device_token_delegates_to_repository(self):
        user = SimpleNamespace(id=1, device_token=None)
        repository = SimpleNamespace(
            update_device_token=lambda user, device_token: SimpleNamespace(
                id=user.id,
                device_token=device_token,
            )
        )
        service = MobileApiService(db=None, repository=repository)

        result = service.update_user_device_token(user=user, device_token="token123")

        assert result.device_token == "token123"

    def test_mark_notification_as_read_delegates_to_repository(self):
        repository = SimpleNamespace(mark_notification_read=lambda notification: True)
        service = MobileApiService(db=None, repository=repository)

        assert service.mark_notification_as_read(notification=SimpleNamespace(id=1))


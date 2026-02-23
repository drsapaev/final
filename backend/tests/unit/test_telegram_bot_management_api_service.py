from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.telegram_bot_management_api_service import (
    TelegramBotManagementApiService,
)


@pytest.mark.unit
class TestTelegramBotManagementApiService:
    def test_get_stats_payload_uses_repository_counts(self):
        repository = SimpleNamespace(
            count_users_with_telegram=lambda: 10,
            count_active_users_with_telegram=lambda: 7,
            count_admin_users_with_telegram=lambda: 2,
            list_active_user_ids_with_telegram=lambda: [],
            list_users_with_telegram=lambda: [],
        )
        service = TelegramBotManagementApiService(db=None, repository=repository)

        payload = service.get_stats_payload()

        assert payload["total_users"] == 10
        assert payload["active_users"] == 7
        assert payload["admin_users"] == 2
        assert payload["messages_sent_today"] == 0

    def test_list_active_user_recipients_returns_ids(self):
        repository = SimpleNamespace(
            count_users_with_telegram=lambda: 0,
            count_active_users_with_telegram=lambda: 0,
            count_admin_users_with_telegram=lambda: 0,
            list_active_user_ids_with_telegram=lambda: [1, 2, 3],
            list_users_with_telegram=lambda: [],
        )
        service = TelegramBotManagementApiService(db=None, repository=repository)

        recipients = service.list_active_user_recipients()

        assert recipients == [1, 2, 3]
        assert service.count_admin_recipients() == 0

    def test_get_users_with_telegram_payload_maps_user_fields(self):
        repository = SimpleNamespace(
            count_users_with_telegram=lambda: 0,
            count_active_users_with_telegram=lambda: 0,
            count_admin_users_with_telegram=lambda: 0,
            list_active_user_ids_with_telegram=lambda: [],
            list_users_with_telegram=lambda: [
                SimpleNamespace(
                    id=5,
                    username="user5",
                    full_name="User Five",
                    role="Doctor",
                    telegram_chat_id="12345",
                    is_active=True,
                    created_at=datetime(2026, 2, 1, 10, 0, 0),
                )
            ],
        )
        service = TelegramBotManagementApiService(db=None, repository=repository)

        payload = service.get_users_with_telegram_payload()

        assert payload["total_count"] == 1
        assert payload["users"][0]["username"] == "user5"
        assert payload["users"][0]["telegram_chat_id"] == "12345"

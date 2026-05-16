from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest

from app.api.v1.endpoints import admin_telegram
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

    def test_staff_link_start_token_round_trips_with_hash_only_contract(self):
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        token = admin_telegram.build_staff_link_start_token(
            user_id=42,
            chat_id=998877,
            expires_at=expires_at,
            nonce="unitnonce",
        )
        parsed = admin_telegram.parse_staff_link_start_token(token)

        assert parsed is not None
        assert parsed["user_id"] == 42
        assert parsed["chat_id"] == 998877
        assert parsed["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )

    def test_staff_link_start_token_validator_reports_expired_reason(self):
        token = admin_telegram.build_staff_link_start_token(
            user_id=42,
            chat_id=998877,
            expires_at=datetime.now(timezone.utc) - timedelta(minutes=1),
            nonce="expirednonce",
        )

        result = admin_telegram.validate_staff_link_start_token(
            db=object(),
            token=token,
            telegram_chat_id=998877,
        )

        assert result["valid"] is False
        assert result["reason"] == "expired"
        assert result["token_hash"].startswith(
            admin_telegram.STAFF_LINK_TOKEN_HASH_PREFIX
        )
        assert admin_telegram.parse_staff_link_start_token(token) is None

    def test_staff_link_start_token_validator_accepts_active_staff(
        self, monkeypatch
    ):
        token = admin_telegram.build_staff_link_start_token(
            user_id=42,
            chat_id=998877,
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=10),
            nonce="validnonce",
        )
        user = SimpleNamespace(id=42, role="Laboratory", is_active=True)

        class FakeQuery:
            def filter(self, *_args, **_kwargs):
                return self

            def first(self):
                return user

        db = SimpleNamespace(query=lambda _model: FakeQuery())
        monkeypatch.setattr(
            admin_telegram.crud_telegram,
            "get_telegram_user_by_chat_id",
            lambda _db, _chat_id: SimpleNamespace(user_id=None),
        )
        monkeypatch.setattr(
            admin_telegram.crud_telegram,
            "get_telegram_user_by_linked_user_id",
            lambda _db, _linked_user_id: None,
        )

        result = admin_telegram.validate_staff_link_start_token(
            db=db,
            token=token,
            telegram_chat_id=998877,
        )

        assert result["valid"] is True
        assert result["reason"] == "ok"
        assert result["user_id"] == 42
        assert result["chat_id"] == 998877
        assert result["role"] == "lab"
        assert result["single_use_enforced"] is False

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import telegram_webhook
from app.models.audit import AuditLog
from app.models.telegram_config import TelegramUser


class FakeTelegramBotService:
    def __init__(self):
        self._send_message = AsyncMock(return_value=True)


def _link_staff_chat(db_session, *, chat_id: int, user_id: int) -> TelegramUser:
    telegram_user = TelegramUser(
        chat_id=chat_id,
        user_id=user_id,
        username="staff_chat",
        first_name="Staff",
        language_code="ru",
        notifications_enabled=False,
        appointment_reminders=False,
        lab_notifications=False,
        active=True,
        blocked=False,
    )
    db_session.add(telegram_user)
    db_session.commit()
    db_session.refresh(telegram_user)
    return telegram_user


@pytest.mark.unit
class TestTelegramStaffReadOnlyMenuRuntime:
    @pytest.mark.asyncio
    async def test_staff_command_returns_read_only_role_menu(
        self, db_session, admin_user
    ):
        _link_staff_chat(db_session, chat_id=7201, user_id=admin_user.id)
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 201,
            "message": {
                "message_id": 1,
                "chat": {"id": 7201},
                "from": {"id": 7201},
                "text": "/staff",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        chat_id, text, reply_markup = fake_service._send_message.await_args.args
        assert chat_id == 7201
        assert "Staff read-only menu" in text
        assert "Role: admin" in text
        assert "State-changing actions are disabled" in text
        assert reply_markup["resize_keyboard"] is True
        assert ["/staff", "/help"] == [
            item["text"] for item in reply_markup["keyboard"][-1]
        ]
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.actor_user_id == admin_user.id
        assert audit_log.entity_id is not None
        assert audit_log.payload["actor_role"] == "admin"
        assert audit_log.payload["command_key"] == "/staff"
        assert audit_log.payload["menu_item_key"] == "staff_menu"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False
        assert "telegram_chat:" in audit_log.payload["telegram_user_id_hash"]
        assert "7201" not in str(audit_log.payload)

    @pytest.mark.asyncio
    async def test_staff_read_only_command_does_not_execute_patient_queue(
        self, db_session, admin_user
    ):
        _link_staff_chat(db_session, chat_id=7202, user_id=admin_user.id)
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 202,
            "message": {
                "message_id": 1,
                "chat": {"id": 7202},
                "from": {"id": 7202},
                "text": "/queue",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once()
        assert (
            fake_service._send_message.await_args.args[1]
            == telegram_webhook.TELEGRAM_STAFF_MENU_PLACEHOLDER_MESSAGE
        )
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.actor_user_id == admin_user.id
        assert audit_log.payload["command_key"] == "/queue"
        assert audit_log.payload["read_only"] is True
        assert audit_log.payload["state_changing_action"] is False

    @pytest.mark.asyncio
    async def test_unlinked_staff_menu_request_does_not_create_patient_link(
        self, db_session
    ):
        fake_service = FakeTelegramBotService()
        update = {
            "update_id": 203,
            "message": {
                "message_id": 1,
                "chat": {"id": 7203},
                "from": {"id": 7203},
                "text": "/staff",
            },
        }

        handled = await telegram_webhook._handle_clinic_bot_update(
            update, db_session, fake_service
        )

        assert handled is True
        fake_service._send_message.assert_awaited_once_with(
            7203,
            telegram_webhook.TELEGRAM_STAFF_MENU_UNLINKED_MESSAGE,
            telegram_webhook.TELEGRAM_STAFF_LINK_REPLY_MARKUP,
        )
        assert (
            db_session.query(TelegramUser)
            .filter(TelegramUser.chat_id == 7203)
            .first()
            is None
        )
        audit_log = (
            db_session.query(AuditLog)
            .filter(AuditLog.action == "staff_command_received")
            .one()
        )
        assert audit_log.actor_user_id is None
        assert audit_log.entity_id is None
        assert audit_log.payload["actor_role"] == "unlinked"
        assert audit_log.payload["command_key"] == "/staff"
        assert audit_log.payload["result"] == "denied"
        assert audit_log.payload["reason"] == "staff_not_linked"
        assert "telegram_chat:" in audit_log.payload["telegram_user_id_hash"]
        assert "7203" not in str(audit_log.payload)

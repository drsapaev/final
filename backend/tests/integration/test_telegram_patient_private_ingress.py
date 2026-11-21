"""Use the real authenticated webhook, with every provider call mocked."""

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import telegram_webhook
from app.models.telegram_config import TelegramConfig, TelegramUser
from app.services import telegram_webhook_dedup
from app.services.telegram_bot import TelegramBotService
from app.services.visit_confirmation_service import (
    _hash_telegram_ticket_start_token,
    build_telegram_ticket_start_token,
)


@pytest.fixture
def bot(db_session, monkeypatch):
    config = db_session.query(TelegramConfig).first() or TelegramConfig()
    config.bot_token = "SYNTHETIC-bot-credential"
    config.webhook_secret = "SYNTHETIC-webhook-secret"
    config.active = True
    db_session.add(config)
    db_session.commit()
    service = TelegramBotService()
    service.active = True
    service.bot_token = "SYNTHETIC-bot-credential"
    service._send_message = AsyncMock(return_value=True)
    service._answer_callback_query = AsyncMock(return_value=True)
    service._httpx_post = AsyncMock()
    monkeypatch.setattr(telegram_webhook, "get_telegram_bot_service", AsyncMock(return_value=service))
    monkeypatch.setattr(telegram_webhook_dedup, "resolve_ledger_bot_identity", AsyncMock(return_value="SYNTHETIC-bot"))
    return service


def _post(client, message):
    return client.post("/api/v1/telegram/webhook", json={"message": message},
                       headers={"x-telegram-bot-api-secret-token": "SYNTHETIC-webhook-secret"})


@pytest.mark.parametrize("chat_type", ["group", "supergroup", "channel"])
def test_legacy_group_link_never_reads_patient_menu(client, db_session, test_patient, test_visit, bot, chat_type):
    group_id = -370015
    db_session.add(TelegramUser(chat_id=group_id, patient_id=test_patient.id, active=True, blocked=False))
    db_session.commit()
    message = {"message_id": 1, "chat": {"id": group_id, "type": chat_type},
               "from": {"id": 370015}, "text": "/profile"}
    response = _post(client, message)
    assert response.status_code == 200
    bot._send_message.assert_not_awaited()


def test_group_contact_cannot_link_patient(client, db_session, test_patient, bot):
    actor, group_id = 370016, -370016
    message = {"message_id": 2, "chat": {"id": group_id, "type": "group"}, "from": {"id": actor},
               "contact": {"user_id": actor, "phone_number": test_patient.phone}}
    assert _post(client, message).status_code == 200
    db_session.expire_all()
    assert db_session.query(TelegramUser).filter_by(chat_id=group_id, patient_id=test_patient.id).first() is None
    bot._send_message.assert_not_awaited()


def test_group_ticket_never_consumes_or_links(client, db_session, test_visit, bot):
    group_id = -370017
    ticket = build_telegram_ticket_start_token(expires_at=datetime.now(UTC) + timedelta(minutes=10))
    ticket_hash = _hash_telegram_ticket_start_token(ticket)
    test_visit.status = "open"
    test_visit.confirmation_token = ticket_hash
    test_visit.confirmation_expires_at = datetime.now(UTC) + timedelta(minutes=10)
    db_session.commit()
    message = {"message_id": 3, "chat": {"id": group_id, "type": "supergroup"},
               "from": {"id": 370017}, "text": f"/start {ticket}"}
    assert _post(client, message).status_code == 200
    db_session.expire_all()
    assert db_session.get(type(test_visit), test_visit.id).confirmation_token == ticket_hash
    assert db_session.query(TelegramUser).filter_by(chat_id=group_id).first() is None
    bot._send_message.assert_not_awaited()


def test_matching_private_actor_can_read_existing_link(client, db_session, test_patient, test_visit, bot):
    actor = 370018
    db_session.add(TelegramUser(chat_id=actor, patient_id=test_patient.id, active=True, blocked=False))
    db_session.commit()
    message = {"message_id": 4, "chat": {"id": actor, "type": "private"}, "from": {"id": actor}, "text": "/visits"}
    assert _post(client, message).status_code == 200
    assert bot._send_message.await_count == 1


@pytest.mark.parametrize("chat,sender", [
    ({"id": 370019, "type": "private"}, {"id": 370020}),
    ({"id": 370019}, {"id": 370019}),
    ({"id": 370019, "type": "private"}, {"id": True}),
    ({"id": -370019, "type": "private"}, {"id": -370019}),
])
def test_patient_menu_requires_verified_matching_private_actor(client, db_session, test_patient, bot, chat, sender):
    db_session.add(TelegramUser(chat_id=370019, patient_id=test_patient.id, active=True, blocked=False))
    db_session.commit()
    assert _post(client, {"message_id": 5, "chat": chat, "from": sender, "text": "/profile"}).status_code == 200
    bot._send_message.assert_not_awaited()


@pytest.mark.parametrize("active,blocked", [(False, False), (True, True)])
def test_private_menu_never_reads_inactive_or_blocked_link(client, db_session, test_patient, bot, active, blocked):
    actor = 370021
    test_patient.last_name = "SYNTHETIC-PRIVATE"
    db_session.add(TelegramUser(chat_id=actor, patient_id=test_patient.id, active=active, blocked=blocked))
    db_session.commit()
    assert _post(client, {"message_id": 6, "chat": {"id": actor, "type": "private"},
                          "from": {"id": actor}, "text": "/profile"}).status_code == 200
    assert bot._send_message.await_count == 1
    assert "SYNTHETIC-PRIVATE" not in str(bot._send_message.await_args)


def test_staff_dispatch_remains_before_patient_private_guard(client, monkeypatch, bot):
    from app.api.v1.endpoints.telegram_webhook import _clinic_bot

    staff = AsyncMock(return_value=True)
    monkeypatch.setattr(_clinic_bot, "_handle_staff_read_only_menu", staff)
    message = {"message_id": 7, "chat": {"id": -370022, "type": "group"},
               "from": {"id": 370022}, "text": "/staff"}
    assert _post(client, message).status_code == 200
    staff.assert_awaited_once()

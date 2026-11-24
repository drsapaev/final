"""Legacy Telegram fallback: private account metadata and static help only."""

from unittest.mock import AsyncMock

import pytest

from app.models.telegram_config import TelegramUser
from app.services.telegram_bot import TelegramBotService

CHAT_ID = 9876543210


def _message(text: str, *, chat_type="private", sender_id=CHAT_ID, name="Synthetic"):
    return {
        "message": {
            "chat": {"id": CHAT_ID, "type": chat_type},
            "from": {"id": sender_id, "first_name": name, "language_code": "ru"},
            "text": text,
        }
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["SYNTHETIC_NOTE", "Какой адрес?", "Сколько стоит?"])
async def test_private_text_creates_unlinked_profile_and_replies_without_echo(
    db_session, monkeypatch, text,
):
    bot = TelegramBotService()
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(bot, "send_plain_message", send)

    await bot.process_webhook_update(_message(text), db_session)

    row = db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).one()
    assert row.user_id is None and row.patient_id is None
    assert not row.notifications_enabled
    send.assert_awaited_once()
    destination, reply = send.await_args.args
    assert destination == CHAT_ID
    assert "/start" in reply and text not in reply


@pytest.mark.asyncio
async def test_private_profile_updates_existing_row_without_enabling_notifications(
    db_session, monkeypatch,
):
    row = TelegramUser(chat_id=CHAT_ID, first_name="Old", notifications_enabled=False)
    db_session.add(row)
    db_session.commit()
    original_id = row.id
    bot = TelegramBotService()
    monkeypatch.setattr(bot, "send_plain_message", AsyncMock(return_value=True))

    await bot.process_webhook_update(_message("SYNTHETIC_NOTE", name="New"), db_session)

    updated = db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).one()
    assert updated.id == original_id
    assert updated.first_name == "New" and updated.last_activity is not None
    assert not updated.notifications_enabled
    assert updated.user_id is None and updated.patient_id is None


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type,sender_id", [("group", CHAT_ID), ("private", 12)])
async def test_wrong_identity_cannot_create_profile_or_get_reply(
    db_session, monkeypatch, chat_type, sender_id,
):
    bot = TelegramBotService()
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(bot, "send_plain_message", send)
    registration = AsyncMock()
    monkeypatch.setattr(bot, "_register_telegram_user", registration)

    await bot.process_webhook_update(
        _message("SYNTHETIC_NOTE", chat_type=chat_type, sender_id=sender_id),
        db_session,
    )

    registration.assert_not_awaited()
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_blocked_private_profile_is_not_updated_or_replied_to(
    db_session, monkeypatch,
):
    row = TelegramUser(chat_id=CHAT_ID, first_name="Old", blocked=True)
    db_session.add(row)
    db_session.commit()
    bot = TelegramBotService()
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(bot, "send_plain_message", send)

    await bot.process_webhook_update(_message("SYNTHETIC_NOTE", name="New"), db_session)

    db_session.refresh(row)
    assert row.first_name == "Old" and row.blocked
    send.assert_not_awaited()


@pytest.mark.asyncio
async def test_linked_private_profile_keeps_clinic_binding_and_escapes_welcome(
    db_session, test_patient, monkeypatch,
):
    row = TelegramUser(
        chat_id=CHAT_ID,
        patient_id=test_patient.id,
        first_name="Old",
        notifications_enabled=True,
    )
    db_session.add(row)
    db_session.commit()
    old_epoch = row.patient_link_epoch
    bot = TelegramBotService()
    send = AsyncMock(return_value=True)
    monkeypatch.setattr(bot, "_send_message", send)

    await bot.process_webhook_update(
        _message("/start", name="<b>Synthetic</b>"), db_session
    )

    db_session.refresh(row)
    assert row.patient_id == test_patient.id and row.user_id is None
    assert row.notifications_enabled and row.patient_link_epoch == old_epoch
    send.assert_awaited_once()
    assert "&lt;b&gt;Synthetic&lt;/b&gt;" in send.await_args.args[1]
    assert "<b>Synthetic</b>" not in send.await_args.args[1]

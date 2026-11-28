"""Legacy Telegram fallback: private account metadata and static help only."""

from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints import telegram_webhook
from app.models.telegram_config import TelegramUser
from app.services.telegram_bot import TelegramBotService

CHAT_ID = 9876543210


def _message(
    text: str,
    *,
    chat_type="private",
    sender_id=CHAT_ID,
    name="Synthetic",
    language="ru",
):
    return {
        "message": {
            "chat": {"id": CHAT_ID, "type": chat_type},
            "from": {"id": sender_id, "first_name": name, "language_code": language},
            "text": text,
        }
    }


async def _dispatch_with_legacy(update, db, bot):
    handled = await telegram_webhook._handle_clinic_bot_update(update, db, bot)
    if not handled:
        await bot.process_webhook_update(update, db)
    return handled


@pytest.fixture
def bot(monkeypatch):
    service = TelegramBotService()
    monkeypatch.setattr(service, "send_plain_message", AsyncMock(return_value=True))
    monkeypatch.setattr(service, "_send_message", AsyncMock(return_value=True))
    return service


def _assert_private_hint(bot, menu_label):
    bot._send_message.assert_not_awaited()
    bot.send_plain_message.assert_awaited_once()
    recipient, message = bot.send_plain_message.await_args.args
    assert recipient == CHAT_ID
    assert "/start" in message and menu_label in message.casefold()
    assert "synthetic" not in message.casefold()


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["SYNTHETIC_NOTE", "Какой адрес?", "Сколько стоит?"])
async def test_private_text_creates_unlinked_profile_and_replies_without_echo(
    db_session,
    bot,
    text,
):
    await bot.process_webhook_update(_message(text), db_session)

    row = db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).one()
    assert row.user_id is None and row.patient_id is None
    assert not row.notifications_enabled
    bot.send_plain_message.assert_awaited_once()
    destination, reply = bot.send_plain_message.await_args.args
    assert destination == CHAT_ID
    assert "/start" in reply and text not in reply


@pytest.mark.asyncio
@pytest.mark.parametrize(("language", "menu_label"), [("ru", "меню"), ("uz", "menyu")])
async def test_clinic_dispatch_routes_new_private_text_to_localized_legacy_reply(
    db_session, bot, language, menu_label
):
    handled = await _dispatch_with_legacy(
        _message("SYNTHETIC-NOTE", name="SYNTHETIC-Profile", language=language),
        db_session,
        bot,
    )

    assert handled is False
    profile = db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).one()
    assert profile.first_name == "SYNTHETIC-Profile"
    assert profile.last_activity is not None
    assert profile.user_id is None and profile.patient_id is None
    assert not profile.notifications_enabled
    _assert_private_hint(bot, menu_label)


@pytest.mark.asyncio
async def test_private_profile_updates_existing_row_without_enabling_notifications(
    db_session,
    bot,
):
    row = TelegramUser(chat_id=CHAT_ID, first_name="Old", notifications_enabled=False)
    db_session.add(row)
    db_session.commit()
    original_id = row.id
    await bot.process_webhook_update(_message("SYNTHETIC_NOTE", name="New"), db_session)

    updated = db_session.query(TelegramUser).filter_by(chat_id=CHAT_ID).one()
    assert updated.id == original_id
    assert updated.first_name == "New" and updated.last_activity is not None
    assert not updated.notifications_enabled
    assert updated.user_id is None and updated.patient_id is None


@pytest.mark.asyncio
async def test_clinic_fallback_preserves_linked_profile_preferences_and_language(
    db_session, test_patient, bot
):
    profile = TelegramUser(
        chat_id=CHAT_ID,
        patient_id=test_patient.id,
        first_name="SYNTHETIC-Old",
        language_code="uz-Latn",
        notifications_enabled=True,
        appointment_reminders=False,
        lab_notifications=True,
    )
    db_session.add(profile)
    db_session.commit()
    epoch = profile.patient_link_epoch

    handled = await _dispatch_with_legacy(
        _message("SYNTHETIC-NOTE", name="SYNTHETIC-New", language="ru"), db_session, bot
    )

    assert handled is False
    db_session.refresh(profile)
    assert profile.first_name == "SYNTHETIC-New" and profile.last_activity is not None
    assert profile.patient_id == test_patient.id and profile.patient_link_epoch == epoch
    assert profile.language_code == "uz-Latn"
    assert profile.notifications_enabled and profile.lab_notifications
    assert not profile.appointment_reminders
    _assert_private_hint(bot, "menyu")


@pytest.mark.asyncio
@pytest.mark.parametrize("chat_type,sender_id", [("group", CHAT_ID), ("private", 12)])
async def test_wrong_identity_cannot_create_profile_or_get_reply(
    db_session,
    bot,
    monkeypatch,
    chat_type,
    sender_id,
):
    registration = AsyncMock()
    monkeypatch.setattr(bot, "_register_telegram_user", registration)

    await bot.process_webhook_update(
        _message("SYNTHETIC_NOTE", chat_type=chat_type, sender_id=sender_id),
        db_session,
    )

    registration.assert_not_awaited()
    bot.send_plain_message.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize(("active", "blocked"), [(True, True), (False, False)])
@pytest.mark.parametrize("through_clinic", [False, True], ids=["legacy", "clinic"])
async def test_unavailable_private_profile_is_not_updated_or_replied_to(
    db_session, bot, active, blocked, through_clinic
):
    row = TelegramUser(
        chat_id=CHAT_ID,
        first_name="SYNTHETIC-Old",
        language_code="uz-Latn",
        active=active,
        blocked=blocked,
    )
    db_session.add(row)
    db_session.commit()

    update = _message("SYNTHETIC-NOTE", name="SYNTHETIC-New", language="ru")
    if through_clinic:
        await _dispatch_with_legacy(update, db_session, bot)
    else:
        await bot.process_webhook_update(update, db_session)

    db_session.refresh(row)
    assert row.first_name == "SYNTHETIC-Old" and row.last_activity is None
    assert row.language_code == "uz-Latn"
    assert row.active is active and row.blocked is blocked
    bot.send_plain_message.assert_not_awaited()
    bot._send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_linked_private_profile_keeps_clinic_binding_and_escapes_welcome(
    db_session,
    test_patient,
    bot,
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

    await bot.process_webhook_update(
        _message("/start", name="<b>Synthetic</b>"), db_session
    )

    db_session.refresh(row)
    assert row.patient_id == test_patient.id and row.user_id is None
    assert row.notifications_enabled and row.patient_link_epoch == old_epoch
    bot._send_message.assert_awaited_once()
    reply = bot._send_message.await_args.args[1]
    assert "&lt;b&gt;Synthetic&lt;/b&gt;" in reply
    assert "<b>Synthetic</b>" not in reply

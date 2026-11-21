"""Outgoing patient messages keep Telegram Markdown syntax and delivery truth."""
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.appointment_rsvp import parse_appointment_callback
from app.services.telegram.bot import ClinicTelegramBot


@pytest.mark.asyncio
async def test_reminder_is_neutral_and_contains_only_view_button():
    bot = ClinicTelegramBot()
    bot.send_notification = AsyncMock(return_value=True)
    result = await bot.send_appointment_reminder(413371, {
        "id": 17, "occurrence_revision": 4, "telegram_link_id": 7, "patient_link_epoch": 2, "doctor": "DOC_[A]*X`",
        "date": "D_[A]", "time": "T_*X",
    })
    assert result is True
    args = bot.send_notification.await_args.args
    assert "DOC" not in args[1]
    assert "D_[A]" not in args[1]
    assert "T_*X" not in args[1]
    buttons = args[2].inline_keyboard[0]
    assert len(buttons) == 1
    assert parse_appointment_callback(buttons[0].callback_data)[0] == "v"
    assert len(buttons[0].callback_data.encode()) <= 64


@pytest.mark.asyncio
async def test_reminder_without_occurrence_never_sends():
    bot = ClinicTelegramBot()
    bot.send_notification = AsyncMock(return_value=True)
    assert not await bot.send_appointment_reminder(413371, {"id": 17})
    bot.send_notification.assert_not_awaited()


@pytest.mark.asyncio
async def test_lab_escapes_both_fields_and_propagates_failure():
    bot = ClinicTelegramBot()
    bot.send_notification = AsyncMock(return_value=False)
    assert not await bot.send_lab_results_ready(413371, {"test_name": "SYN_[A]*", "date": "D_[B]*"})
    message = bot.send_notification.await_args.args[1]
    assert r"SYN\_\[A\]\*" in message
    assert r"D\_\[B\]\*" in message


@pytest.mark.asyncio
async def test_invitation_provider_error_does_not_leak_message_or_token(caplog):
    bot = ClinicTelegramBot()
    marker = "SYNTHETIC_CLINICAL_MARKER"
    bot.bot = SimpleNamespace(send_message=AsyncMock(side_effect=RuntimeError(marker)))

    result = await bot.send_confirmation_invitation(413371, "private", [])

    assert result == {"success": False, "error": "Telegram delivery failed"}
    assert marker not in caplog.text

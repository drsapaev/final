"""TGCONFIRM-BE-003 (audit #3892, group 20) — bot callback cancel branch.

The bot cancel branch must call the backend cancellation API (same
API_BASE_URL contract as confirm, pinned by TGCONFIRM-BE-001 #4082) and
must NEVER claim "Визит отменен" when the cancellation did not happen.

Run: pytest backend/tests/unit/test_tgconfirm_cancel_callback.py -v
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.telegram.bot import ClinicTelegramBot


class FakeMessage:
    def __init__(self, text: str = "Подтверждение визита 12.11"):
        self.text = text
        self.edited: list[str] = []

    async def edit_text(self, text: str, **kwargs) -> None:
        self.edited.append(text)


class FakeUser:
    id = 777


class FakeCallback:
    def __init__(self):
        self.message = FakeMessage()
        self.from_user = FakeUser()
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


def _bot_with_cancel(monkeypatch, calls: list, payload: dict) -> ClinicTelegramBot:
    bot = ClinicTelegramBot()

    async def fake_cancel(token: str, telegram_user_id: int) -> dict:
        calls.append((token, telegram_user_id))
        return payload

    monkeypatch.setattr(bot, "_cancel_visit_via_api", fake_cancel)
    return bot


@pytest.mark.unit
class TestTgConfirmCancelCallback:
    def test_cancel_callback_calls_api_and_edits_message(self, monkeypatch):
        """RED (TGCONFIRM-BE-003): the cancel branch must call the cancel
        API exactly once with the callback token and only THEN render
        "Визит отменен"."""
        calls: list = []
        bot = _bot_with_cancel(
            monkeypatch,
            calls,
            {"success": True, "message": "Визит отменен", "status": "canceled"},
        )
        cb = FakeCallback()

        result = asyncio.run(bot._handle_visit_confirmation(cb, "tok-9", False))

        assert calls == [("tok-9", 777)], "cancel API must be called once"
        assert result is False
        assert cb.message.edited, "cancel success must edit the message"
        assert "Визит отменен" in cb.message.edited[-1]

    def test_cancel_failure_is_honest(self, monkeypatch):
        """RED: when the API refuses (already confirmed, lease conflict,
        config error) the bot must NOT declare "Визит отменен" — it must
        surface the honest failure alert instead."""
        calls: list = []
        bot = _bot_with_cancel(
            monkeypatch,
            calls,
            {"success": False, "message": "Визит уже подтвержден — отмена невозможна"},
        )
        cb = FakeCallback()

        result = asyncio.run(bot._handle_visit_confirmation(cb, "tok-9", False))

        assert calls == [("tok-9", 777)]
        assert result is True
        assert cb.message.edited == [], "no canceled claim on failure"
        assert cb.answers, "failure must answer the callback"
        last = cb.answers[-1]
        assert "отменить" in last.lower() or "не удалось" in last.lower(), last

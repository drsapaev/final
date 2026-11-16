"""TGCONFIRM-BE-002 (audit #3892, group 20, downstream) — queue render in
the patient Telegram confirm callback.

After TGCONFIRM-BE-001 repaired the API base URL, a successful same-day
confirmation reaches the success-render branch in
``ClinicTelegramBot._handle_visit_confirmation``. That branch formats
every queue entry as ``q['queue_name']``, but the authoritative
``VisitConfirmationService`` queue response builds ``queue_numbers``
entries with ONLY ``queue_tag``, ``number`` and ``queue_id``. The
KeyError therefore fires AFTER the server operation has committed, and
the outer handler shows a generic error for an already-committed
success.

Pinned here:
1. a successful payload with tag-only entries renders an acknowledgment
   containing a human-readable label derived from ``queue_tag``
   (no KeyError, no generic error);
2. a UI render/edit failure AFTER the committed confirmation never
   repeats the confirmation call and tells the patient the confirmation
   itself succeeded.

No real Telegram API, no real backend HTTP call: ``_confirm_visit_via_api``
is stubbed with the authoritative payload shape.

Run: pytest backend/tests/unit/test_tgconfirm_queue_render.py -v
"""
from __future__ import annotations

import asyncio

import pytest

from app.services.telegram.bot import ClinicTelegramBot


class FakeMessage:
    def __init__(self, text: str = "Визит 12.11, кардиология", *, edit_raises=None):
        self.text = text
        self.edited: list[str] = []
        self._edit_raises = edit_raises

    async def edit_text(self, text: str, **kwargs) -> None:
        if self._edit_raises is not None:
            raise self._edit_raises
        self.edited.append(text)


class FakeUser:
    id = 777


class FakeCallback:
    def __init__(self, *, edit_raises=None):
        self.message = FakeMessage(edit_raises=edit_raises)
        self.from_user = FakeUser()
        self.answers: list[str] = []

    async def answer(self, text: str, **kwargs) -> None:
        self.answers.append(text)


def _bot_with_confirm(monkeypatch, calls: list, payload: dict) -> ClinicTelegramBot:
    bot = ClinicTelegramBot()

    async def fake_confirm(token: str, telegram_user_id: int) -> dict:
        calls.append((token, telegram_user_id))
        return payload

    monkeypatch.setattr(bot, "_confirm_visit_via_api", fake_confirm)
    return bot


SUCCESS_TAG_ONLY_PAYLOAD = {
    "success": True,
    "message": "confirmed",
    "queue_numbers": [
        {"queue_tag": "cardiology_common", "number": 2, "queue_id": 1}
    ],
}


@pytest.mark.unit
class TestTgConfirmQueueRender:
    def test_success_payload_with_tag_only_entries_renders_label(
        self, monkeypatch
    ):
        """RED (TGCONFIRM-BE-002): the authoritative queue payload has
        queue_tag/number/queue_id — rendering must NOT raise KeyError,
        must include a readable label and the ticket number, and must
        not show the generic error for a committed success."""
        calls: list = []
        bot = _bot_with_confirm(monkeypatch, calls, SUCCESS_TAG_ONLY_PAYLOAD)
        cb = FakeCallback()

        result = asyncio.run(bot._handle_visit_confirmation(cb, "tok-1", True))

        assert calls == [("tok-1", 777)]
        assert result is False
        assert cb.answers == [], cb.answers
        assert cb.message.edited, "success branch must edit the message"
        rendered = cb.message.edited[-1]
        assert "cardiology_common" in rendered
        assert "№2" in rendered
        assert "Визит успешно подтвержден" in rendered

    def test_render_failure_after_commit_never_reconfirms(
        self, monkeypatch
    ):
        """Audit-required retry messaging: if the UI edit fails AFTER the
        confirmation committed, the confirm call must NOT be repeated and
        the patient must be told the confirmation itself succeeded —
        not the generic 'Произошла ошибка при подтверждении'."""
        calls: list = []
        bot = _bot_with_confirm(monkeypatch, calls, SUCCESS_TAG_ONLY_PAYLOAD)
        cb = FakeCallback(edit_raises=RuntimeError("telegram edit failed"))

        result = asyncio.run(bot._handle_visit_confirmation(cb, "tok-1", True))

        assert calls == [("tok-1", 777)], "confirm must run exactly once"
        assert result is True
        assert cb.answers, "outer handler must answer the callback"
        last = cb.answers[-1]
        assert "подтвержден" in last.lower() or "подтверждён" in last.lower(), (
            f"already-committed success must be communicated, got: {last!r}"
        )
        assert "Произошла ошибка при подтверждении" not in last

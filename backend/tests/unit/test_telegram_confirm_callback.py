"""Telegram visit decisions use a verified in-process service boundary."""

import asyncio
from unittest.mock import Mock

from app.services.telegram import bot as bot_module
from app.services.telegram.bot import ClinicTelegramBot


def test_visit_decisions_use_internal_service_with_actor_and_close_session(monkeypatch):
    calls = []
    session = Mock()
    session.__enter__ = Mock(return_value=session)
    session.__exit__ = Mock(return_value=False)

    class FakeService:
        def __init__(self, db):
            assert db is session

        def confirm_by_telegram(self, **kwargs):
            calls.append(("confirm", kwargs))
            return {"success": True}

        def cancel_by_telegram(self, **kwargs):
            calls.append(("cancel", kwargs))
            return {"success": True}

    monkeypatch.setattr(bot_module, "SessionLocal", lambda: session)
    monkeypatch.setattr("app.services.visit_confirmation_service.VisitConfirmationService", FakeService)
    bot = ClinicTelegramBot()
    assert asyncio.run(bot._confirm_visit_via_api("SYNTHETIC", 777))["success"]
    assert asyncio.run(bot._cancel_visit_via_api("SYNTHETIC", 777))["success"]
    assert [kind for kind, _ in calls] == ["confirm", "cancel"]
    assert all(value["telegram_user_id"] == "777" for _, value in calls)
    assert session.__exit__.call_count == 2


def test_visit_internal_failure_is_generic(monkeypatch, caplog):
    def fail(*args):
        raise RuntimeError("SYNTHETIC_PRIVATE_MARKER")

    monkeypatch.setattr(bot_module, "_run_visit_decision", fail)
    bot = ClinicTelegramBot()
    result = asyncio.run(bot._confirm_visit_via_api("SYNTHETIC", 777))
    assert result["success"] is False
    assert "SYNTHETIC_PRIVATE_MARKER" not in repr(result)
    assert "SYNTHETIC_PRIVATE_MARKER" not in caplog.text

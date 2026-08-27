"""Scheduler contract: run_lab_notifications orchestrates all three checks.

Regression for the production warning fired every 5 minutes:
`LabNotificationService' object has no attribute 'run_all_notifications'`
— app/main.py called a method removed in the lab-service refactor while
the module-level orchestrator run_lab_notifications(db) is the canonical
entrypoint. This test pins the orchestrator's contract.
"""
from __future__ import annotations

import pytest

from app.services import lab_notification_service as mod


@pytest.mark.asyncio
async def test_run_lab_notifications_calls_all_three_checks(monkeypatch):
    calls: list[str] = []

    async def fake_ready(self):
        calls.append("ready")
        return {"notified": 1}

    async def fake_critical(self):
        calls.append("critical")
        return {"alerted": 0}

    async def fake_follow_up(self, days_before: int = 3):
        calls.append("follow_up")
        return {"sent": 0}

    monkeypatch.setattr(
        mod.LabNotificationService, "check_and_notify_ready_results", fake_ready
    )
    monkeypatch.setattr(
        mod.LabNotificationService, "check_critical_values", fake_critical
    )
    monkeypatch.setattr(
        mod.LabNotificationService, "send_follow_up_reminders", fake_follow_up
    )

    class _FakeDB:
        pass

    result = await mod.run_lab_notifications(_FakeDB())  # type: ignore[arg-type]

    assert calls == ["ready", "critical", "follow_up"]
    assert set(result) == {
        "ready_results",
        "critical_values",
        "follow_up_reminders",
        "timestamp",
    }


@pytest.mark.asyncio
async def test_follow_up_reminders_skip_without_data_layer():
    """follow_up_date не существует в модели/БД — метод обязан явно
    возвращать skipped и НЕ бросать исключение (Sentry-регрессия)."""
    result = await mod.LabNotificationService(object()).send_follow_up_reminders()

    assert result == {"skipped": "LabOrder.follow_up_date column does not exist"}


def test_scheduler_module_exposes_orchestrator_not_the_ghost_method():
    # Защита от регрессии вызова: оркестратор существует, «призрак» — нет.
    assert hasattr(mod, "run_lab_notifications")
    assert not hasattr(mod.LabNotificationService, "run_all_notifications")

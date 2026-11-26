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


def test_finalize_enqueues_only_successful_report(
    client, auth_headers, test_patient, test_visit, monkeypatch
):
    from app.api.v1.endpoints import lab_reporting

    queued: list[int] = []
    monkeypatch.setattr(lab_reporting, "run_legacy_report_critical_scan", queued.append)

    base = "/api/v1/lab"
    templates = client.get(f"{base}/templates", headers=auth_headers)
    assert templates.status_code == 200
    template = next(t for t in templates.json() if t["code"] == "cbc_oak")
    draft = client.post(
        f"{base}/report-instances",
        headers=auth_headers,
        json={
            "patient_id": test_patient.id,
            "visit_id": test_visit.id,
            "template_id": template["id"],
        },
    )
    assert draft.status_code == 200, draft.text
    report_id = draft.json()["id"]
    report = f"{base}/report-instances/{report_id}"

    invalid = client.post(
        f"{base}/report-instances/2000000000/finalize", headers=auth_headers
    )
    assert invalid.status_code == 404
    assert not queued

    response = client.post(
        f"{report}/bulk-values",
        headers=auth_headers,
        json=[
            {"field_key": "wbc", "value_text": "6.1"},
            {"field_key": "hgb", "value_text": "140"},
        ],
    )
    assert response.status_code == 200, response.text
    released = client.post(f"{report}/finalize", headers=auth_headers)
    assert released.status_code == 200, released.text
    assert released.json()["status"] == "FINALIZED"
    assert queued == [report_id]

    repeated = client.post(f"{report}/finalize", headers=auth_headers)
    assert repeated.status_code == 409
    assert queued == [report_id]


def test_immediate_scan_owns_context_and_exact_job_scope(monkeypatch):
    from contextlib import contextmanager

    calls = []
    worker_db = object()

    @contextmanager
    def open_session():
        calls.append("open")
        try:
            yield worker_db
        finally:
            calls.append("close")

    async def scan(self, *, report_instance_id):
        calls.append((self.db, report_instance_id))

    monkeypatch.setattr(mod, "SessionLocal", open_session)
    monkeypatch.setattr(mod.LabNotificationService, "check_critical_values", scan)
    mod.run_legacy_report_critical_scan(123)
    assert calls == ["open", (worker_db, 123), "close"]

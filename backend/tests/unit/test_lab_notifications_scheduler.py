"""Scheduler contract: run_lab_notifications orchestrates all three checks.

Regression for the production warning fired every 5 minutes:
`LabNotificationService' object has no attribute 'run_all_notifications'`
— app/main.py called a method removed in the lab-service refactor while
the module-level orchestrator run_lab_notifications(db) is the canonical
entrypoint. This test pins the orchestrator's contract.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select

from app.models.lab import (
    LabOrder,
    LabReportInstance,
    LabReportTemplate,
    LabReportTemplateVersion,
    LabReportValue,
    LabResult,
)
from app.models.lab_critical_communication import LabCriticalCommunication
from app.models.notification import NotificationDelivery, NotificationEvent
from app.services import lab_notification_service as mod
from app.services.notification_platform import NotificationPlatformService


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


@pytest.fixture
def released_result(db_session, test_patient, test_visit):
    order = LabOrder(patient_id=test_patient.id, visit_id=test_visit.id)
    template = LabReportTemplate(
        code="SYNTHETIC-SCHEDULER", name="SYNTHETIC-SCHEDULER", family="SYNTHETIC"
    )
    db_session.add_all([order, template])
    db_session.flush()
    version = LabReportTemplateVersion(
        template_id=template.id, version_no=1, layout_preset="default"
    )
    db_session.add(version)
    db_session.flush()

    def create(
        *, previous=None, status="FINALIZED", managed=False, amount="25",
        evaluation="evaluated", interpretation="critical", snapshot_unit="mmol/L",
        projected_unit="mmol/L", test_name="SYNTHETIC-Глюкоза", snapshot_overrides=None,
        finalized_at=None, projection=None, text_value=None,
    ):
        source = LabReportInstance(
            order_id=order.id,
            visit_id=test_visit.id,
            patient_id=test_patient.id,
            template_id=template.id,
            template_version_id=version.id,
            supersedes_instance_id=previous.id if previous else None,
            status=status,
            managed_release=managed,
            finalized_at=finalized_at or datetime.now(UTC) - timedelta(minutes=10),
        )
        db_session.add(source)
        db_session.flush()
        snapshot = None if evaluation is None else {
            "status": evaluation,
            "interpretation": interpretation,
            "visible": True,
            "template_version_id": version.id,
            "analyte_code": "glucose",
            "unit": snapshot_unit,
            "unit_code": "mmol_per_l",
            "thresholds": {"critical_high": "12"},
        }
        if snapshot_overrides:
            snapshot.update(snapshot_overrides)
        payload = None
        if snapshot is not None:
            payload = {"kind": "numeric" if text_value is None else "text"}
        db_session.add(LabReportValue(
            instance_id=source.id,
            field_key="synthetic_analyte_slot",
            value_numeric=Decimal(amount) if text_value is None else None,
            value_text=text_value,
            result_payload=payload,
            evaluation_snapshot=snapshot,
            resolved_flag_meta={"direction": "high"},
        ))
        if projection is not None:
            projection.source_instance_id = source.id
            projection.value = amount
            projection.unit = projected_unit
            db_session.flush()
            return projection, source
        result = LabResult(
            order_id=order.id,
            source_root_instance_id=previous.id if previous else source.id,
            source_instance_id=source.id,
            test_code="synthetic_analyte_slot",
            test_name=test_name,
            value=amount,
            unit=projected_unit,
            created_at=datetime.now(UTC) - timedelta(days=2),
        )
        db_session.add(result)
        db_session.flush()
        return result, source

    return create


@pytest.mark.asyncio
async def test_scheduler_preserves_historical_alerts_without_duplicating_task_routes(
    db_session, released_result, monkeypatch,
):
    linked, source = released_result()
    historic, historic_source = released_result()
    db_session.add(LabCriticalCommunication(
        report_instance_id=source.id, field_keys=["synthetic_analyte_slot"],
        state="needs_assignment", attempts=0,
    ))
    db_session.flush()
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["critical_found"] == 1
    assert outcome["critical_results"][0]["result_id"] == historic.id
    assert [call.kwargs["metadata"]["report_instance_id"] for call in sender.await_args_list] == [
        historic_source.id, historic_source.id,
    ]
    assert linked.source_instance_id == source.id


@pytest.mark.asyncio
@pytest.mark.parametrize("test_name", [
    "SYNTHETIC-Глюкоза крови", "SYNTHETIC-Қондаги глюкоза", "SYNTHETIC-Qon glyukozasi",
])
async def test_scheduler_uses_frozen_exact_release_without_reading_display_name(
    db_session, released_result, monkeypatch, test_name,
):
    projected, old = released_result(interpretation="normal", amount="13", test_name=test_name)
    _, source = released_result(previous=old, amount="13", projection=projected, test_name=test_name)
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["critical_found"] == 1
    assert [call.kwargs["event_type"] for call in sender.await_args_list] == [
        "lab_critical_result", "lab_critical_finding",
    ]
    for call in sender.await_args_list:
        metadata = call.kwargs["metadata"]
        assert metadata["report_instance_id"] == source.id
        assert metadata["analyte_code"] == "glucose"
        assert metadata["unit_code"] == "mmol_per_l"
        assert metadata["value"] == 13
        assert metadata["critical_high"] == "12"
    assert outcome["critical_results"][0]["unit"] == "mmol/L"


@pytest.mark.asyncio
async def test_scheduler_uses_full_snapshot_unit_for_truncated_projection(
    db_session, released_result, monkeypatch,
):
    unit = "SYNTHETIC validation unit longer than 32 characters"
    released_result(snapshot_unit=unit, projected_unit=unit[:32])
    released_result(snapshot_unit=unit, projected_unit=unit[:31] + "X")
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["critical_found"] == 1
    assert outcome["critical_results"][0]["unit"] == unit
    assert sender.await_count == 2
    assert all(call.kwargs["metadata"]["unit"] == unit for call in sender.await_args_list)


@pytest.mark.asyncio
async def test_scheduler_notifies_for_exact_critical_text_without_copying_raw_finding(
    db_session, released_result, monkeypatch,
):
    finding = "SYNTHETIC critical text " * 6
    result, source = released_result(text_value=finding, amount=finding[:128])
    released_result(text_value=finding, amount=finding[1:129])
    released_result(text_value=finding, amount=finding[:128], interpretation="normal")
    broadcast = AsyncMock()
    monkeypatch.setattr(NotificationPlatformService, "_broadcast_delivery_with_policy", broadcast)
    scheduler = mod.LabNotificationService(db_session)

    outcome = await scheduler.check_critical_values()
    await scheduler.check_critical_values()

    assert outcome["critical_found"] == 1
    assert outcome["critical_results"][0]["result_id"] == result.id
    events = db_session.scalars(select(NotificationEvent).where(
        NotificationEvent.entity_id == str(result.id),
    )).all()
    assert {event.event_type for event in events} == {"lab_critical_result", "lab_critical_finding"}
    assert all(event.payload_snapshot["metadata"]["report_instance_id"] == source.id for event in events)
    assert all("SYNTHETIC critical text" not in str(event.payload_snapshot) for event in events)
    assert broadcast.await_count == 2


@pytest.mark.asyncio
async def test_scheduler_never_shadow_classifies_explicit_noncritical_or_unverified_evidence(
    db_session, released_result, monkeypatch,
):
    for overrides in (
        {"interpretation": "normal"},
        {"evaluation": "not_evaluated"},
        {"evaluation": "unknown"},
        {"projected_unit": "mg/dL"},
        {"status": "IN_PROGRESS"},
        {"managed": True},
        {"snapshot_overrides": {"template_version_id": 987654}},
        {"snapshot_overrides": {"visible": False}},
    ):
        released_result(test_name="SYNTHETIC-glucose", **overrides)
    mismatched_value, _ = released_result(test_name="SYNTHETIC-glucose")
    mismatched_value.value = "35"
    mismatched_lineage, _ = released_result(test_name="SYNTHETIC-glucose")
    mismatched_lineage.source_root_instance_id = None
    mismatched_scope, _ = released_result(test_name="SYNTHETIC-glucose")
    unrelated_order = LabOrder()
    db_session.add(unrelated_order)
    db_session.flush()
    mismatched_scope.order_id = unrelated_order.id
    db_session.flush()
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["critical_found"] == 0
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_keeps_valid_historical_linked_and_unlinked_fallback(
    db_session, released_result, monkeypatch,
):
    linked, source = released_result(evaluation=None, test_name="SYNTHETIC-glucose")
    unlinked = LabResult(
        order_id=linked.order_id, test_name="SYNTHETIC-glucose", value="30", unit=linked.unit,
    )
    db_session.add(unlinked)
    db_session.flush()
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["critical_found"] == 2
    metadata = [call.kwargs["metadata"] for call in sender.await_args_list]
    assert [item["report_instance_id"] for item in metadata if item["result_id"] == linked.id] == [source.id] * 2
    assert all("report_instance_id" not in item for item in metadata if item["result_id"] == unlinked.id)


@pytest.mark.asyncio
async def test_scheduler_does_not_apply_historical_threshold_to_a_different_or_missing_unit(
    db_session, released_result, monkeypatch,
):
    linked, _ = released_result(
        evaluation=None, test_name="SYNTHETIC-glucose", amount="30", projected_unit="mg/dL",
    )
    db_session.add_all([
        LabResult(order_id=linked.order_id, test_name="SYNTHETIC-glucose", value="30", unit=unit)
        for unit in (None, "mg/dL", "mmol/l")
    ])
    db_session.flush()
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["checked"] == 4
    assert outcome["critical_found"] == 0
    sender.assert_not_awaited()


@pytest.mark.asyncio
async def test_scheduler_distinguishes_missing_and_dimensionless_inr_units(
    db_session, released_result, monkeypatch,
):
    linked, _ = released_result(
        evaluation=None, test_name="SYNTHETIC-inr", amount="7", projected_unit=None,
    )
    missing_unit = LabResult(
        order_id=linked.order_id, test_name="SYNTHETIC-inr", value="7", unit=None,
    )
    dimensionless = LabResult(
        order_id=linked.order_id, test_name="SYNTHETIC-inr", value="7", unit="",
    )
    db_session.add_all([missing_unit, dimensionless])
    db_session.flush()
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["checked"] == 3
    assert outcome["critical_found"] == 1
    assert outcome["critical_results"][0]["result_id"] == dimensionless.id


@pytest.fixture
def add_prior_critical_deliveries(db_session, cardio_user):
    old_time = datetime.now(UTC) - timedelta(minutes=2)

    def add(result, source, **overrides):
        metadata = {"value": 25.0, "patient_id": source.patient_id, "unit": "mmol/L"}
        metadata.update(overrides)
        for sequence, event_type in enumerate(("lab_critical_result", "lab_critical_finding"), 1):
            event = NotificationEvent(
                event_type=event_type,
                dedup_key=f"synthetic-old:{event_type}",
                source_module="lab",
                entity_type="lab_result",
                entity_id=str(result.id),
                title="SYNTHETIC",
                message="SYNTHETIC",
                payload_snapshot={"metadata": metadata},
                created_at=old_time,
            )
            db_session.add(NotificationDelivery(
                event=event,
                recipient_type="user",
                recipient_id=cardio_user.id,
                role="Doctor",
                channel="in_app_inbox",
                dedup_key=f"synthetic-old-delivery:{event_type}",
                sequence_id=sequence,
                delivery_status="delivered",
            ))
        db_session.flush()

    return add


@pytest.mark.asyncio
@pytest.mark.parametrize("overrides", [{"unit": "mg/dL"}, {"patient_id": -1}])
async def test_scheduler_does_not_adopt_delivery_for_another_unit_or_patient(
    db_session, released_result, add_prior_critical_deliveries, monkeypatch, overrides,
):
    result, source = released_result()
    add_prior_critical_deliveries(result, source, **overrides)
    broadcast = AsyncMock()
    monkeypatch.setattr(NotificationPlatformService, "_broadcast_delivery_with_policy", broadcast)

    await mod.LabNotificationService(db_session).check_critical_values()

    assert broadcast.await_count == 2


@pytest.mark.asyncio
async def test_scheduler_adopts_prior_delivery_and_deduplicates_identical_corrections_by_release(
    db_session, released_result, add_prior_critical_deliveries, monkeypatch,
):
    result, source = released_result()
    add_prior_critical_deliveries(result, source)
    broadcast = AsyncMock()
    monkeypatch.setattr(NotificationPlatformService, "_broadcast_delivery_with_policy", broadcast)
    scheduler = mod.LabNotificationService(db_session)
    await scheduler.check_critical_values()
    broadcast.assert_not_awaited()

    _, correction = released_result(
        previous=source, finalized_at=datetime.now(UTC), projection=result,
    )
    db_session.commit()
    await scheduler.check_critical_values()
    await scheduler.check_critical_values()

    events = db_session.scalars(select(NotificationEvent).where(
        NotificationEvent.entity_id == str(result.id),
        NotificationEvent.source_module == "lab",
    )).all()
    assert len(events) == 4
    assert sorted(
        event.event_type for event in events
        if event.payload_snapshot["metadata"].get("report_instance_id") == correction.id
    ) == ["lab_critical_finding", "lab_critical_result"]
    assert broadcast.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("interleaved_change", [
    "correction", "reassignment", "doctor_rebound", "doctor_retired",
    "account_deactivated", "account_role_changed",
])
async def test_scheduler_rechecks_release_and_route_after_inbox_commit(
    db_session, released_result, test_visit, test_doctor, test_doctor_user,
    cardio_user, monkeypatch, interleaved_change,
):
    projection, source = released_result()
    original_recipient_id = cardio_user.id

    async def send_and_commit(**kwargs):
        assert kwargs["event_type"] == "lab_critical_result"
        assert kwargs["recipient"].id == original_recipient_id
        if interleaved_change == "correction":
            released_result(
                previous=source, projection=projection, interpretation="normal",
            )
        elif interleaved_change == "reassignment":
            test_visit.doctor_id = None
        elif interleaved_change == "doctor_rebound":
            test_doctor.user_id = test_doctor_user.id
        elif interleaved_change == "doctor_retired":
            test_doctor.active = False
        elif interleaved_change == "account_deactivated":
            cardio_user.is_active = False
        else:
            cardio_user.role = "Registrar"
        db_session.commit()
        if interleaved_change != "reassignment":
            assert test_visit.doctor_id == test_doctor.id
        return True

    sender = AsyncMock(side_effect=send_and_commit)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["critical_found"] == 1
    sender.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("ineligible", ["doctor_retired", "account_deactivated", "account_role_changed"])
async def test_scheduler_skips_linked_results_with_ineligible_recipient(
    db_session, released_result, test_doctor, cardio_user, monkeypatch, ineligible,
):
    released_result()
    if ineligible == "doctor_retired":
        test_doctor.active = False
    elif ineligible == "account_deactivated":
        cardio_user.is_active = False
    else:
        cardio_user.role = "Registrar"
    db_session.flush()
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(mod.notification_sender_service, "send_lab_event_notification", sender)

    outcome = await mod.LabNotificationService(db_session).check_critical_values()

    assert outcome["critical_found"] == 1
    sender.assert_not_awaited()

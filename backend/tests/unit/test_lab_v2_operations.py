from asyncio import run
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from app.core.config import settings
from app.models.audit import AuditLog
from app.models.clinic import Doctor
from app.models.lab import LabOrder, LabReportInstance, LabReportValue
from app.models.lab_critical_communication import LabCriticalCommunicationEvent
from app.models.lab_import import LabImportReceipt
from app.models.lab_release import LabReportCreationReceipt
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.user import User
from app.models.visit import Visit
from app.schemas.lab_import import LabImportBatch
from app.services.authentication_service import authentication_service
from app.services.lab_critical_communication import (
    acknowledge,
    dispatch_pending,
    escalate,
    record_released_report,
)
from app.services.lab_import import process_import_batch
from app.services.lab_operational_metrics import laboratory_metrics
from app.services.lab_reporting import LabReportingDomainError, LabReportingService
from app.services.notifications import notification_sender_service


def synthetic_user(db, role: str) -> User:
    identity = str(uuid4())
    user = User(
        username=f"synthetic-{identity}",
        email=f"{identity}@test.invalid",
        hashed_password="unused",
        full_name=f"SYNTHETIC-{role}",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def synthetic_report(db, patient_id, *, visit_id=None):
    service = LabReportingService(db)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")
    return service, service.create_instance(
        {
            "patient_id": patient_id,
            "visit_id": visit_id,
            "template_id": template.id,
        }
    )


def accepted_specimen(db_session, report, barcode):
    specimen = LabSpecimen(
        order_id=report.order_id,
        barcode=barcode,
        material_code="blood",
        container_code="tube",
        status="accepted",
        revision=1,
        create_request_id=str(uuid4()),
        created_at=datetime.now(UTC),
    )
    db_session.add(specimen)
    db_session.flush()
    db_session.add(
        LabSpecimenAssignment(specimen_id=specimen.id, report_instance_id=report.id)
    )
    db_session.commit()
    return specimen


@pytest.mark.unit
def test_turnaround_uses_elapsed_minutes_for_a_released_specimen(db_session, test_patient):
    _, report = synthetic_report(db_session, test_patient.id)
    specimen = accepted_specimen(db_session, report, "SYNTHETIC-TURNAROUND")
    released_at = datetime.now(UTC) - timedelta(minutes=15)
    specimen.created_at = released_at - timedelta(minutes=65)
    specimen.received_at = released_at - timedelta(minutes=60)
    specimen.accepted_at = specimen.received_at + timedelta(minutes=5)
    assert report.status == "DRAFT"
    report.status = "FINALIZED"
    report.finalized_at = released_at
    db_session.commit()

    metrics = laboratory_metrics(db_session, ZoneInfo("Asia/Tashkent"), days=1)

    assert metrics["turnaround_pairs"] == 1
    assert metrics["average_turnaround_minutes"] == 60.0


@pytest.mark.unit
def test_standalone_does_not_attach_to_old_order(db_session, test_patient, test_visit):
    old_order = LabOrder(
        patient_id=test_patient.id, visit_id=test_visit.id, status="done"
    )
    db_session.add(old_order)
    db_session.commit()

    service, first = synthetic_report(db_session, test_patient.id)
    second = service.create_instance(
        {"patient_id": test_patient.id, "template_id": first.template_id}
    )

    assert len({old_order.id, first.order_id, second.order_id}) == 3
    assert first.visit_id is None and first.order.visit_id is None
    assert second.visit_id is None and second.order.visit_id is None

    orphan = LabOrder(status="ordered")
    db_session.add(orphan)
    db_session.commit()
    with pytest.raises(LabReportingDomainError, match="does not belong to a patient"):
        service.create_instance(
            {
                "patient_id": test_patient.id,
                "template_id": first.template_id,
                "order_id": orphan.id,
            }
        )


@pytest.mark.unit
def test_report_creation_rejects_same_patient_order_from_different_visit(
    client, db_session, admin_auth_headers, test_patient, test_visit
):
    other_visit = Visit(patient_id=test_patient.id, visit_date=test_visit.visit_date)
    order = LabOrder(
        patient_id=test_patient.id, visit_id=test_visit.id, status="ordered"
    )
    db_session.add_all([other_visit, order])
    db_session.commit()
    service = LabReportingService(db_session)
    template = next(item for item in service.list_templates() if item.code == "cbc_oak")

    response = client.post(
        "/api/v1/lab/report-instances",
        headers={**admin_auth_headers, "Idempotency-Key": str(uuid4())},
        json={
            "patient_id": test_patient.id,
            "visit_id": other_visit.id,
            "order_id": order.id,
            "template_id": template.id,
        },
    )

    assert response.status_code == 409, response.text
    assert response.json()["detail"] == "Lab order does not belong to selected visit"
    assert db_session.execute(select(LabOrder.id, LabOrder.visit_id)).all() == [
        (order.id, test_visit.id)
    ]
    assert db_session.scalar(select(LabReportInstance.id)) is None
    assert db_session.scalar(select(LabReportCreationReceipt.instance_id)) is None


@pytest.mark.unit
def test_import_validation_receipt_and_partial_retry(db_session, test_patient):
    actor = synthetic_user(db_session, "Lab")
    service, report = synthetic_report(db_session, test_patient.id)
    specimen = accepted_specimen(db_session, report, "SYNTHETIC-IMPORT")

    field = service._field_map(report.template_version)["hgb"]
    data = {
        "message_id": str(uuid4()),
        "report_instance_id": report.id,
        "specimen_barcode": specimen.barcode,
        "values": [
            {
                "analyte_code": field.field_key,
                "unit_code": service._resolve_field_unit_code(field)
                or service._resolve_field_unit(field),
                "value_text": "<0,01",
            }
        ],
    }

    previews = process_import_batch(
        db_session,
        LabImportBatch(source="manual", rows=[data]),
        actor_id=actor.id,
        preview=True,
    )
    assert previews[0].status == "ready"
    assert db_session.scalar(select(LabImportReceipt.id)) is None
    data["expected_updated_at"] = previews[0].updated_at
    wrong = {**data, "message_id": str(uuid4()), "specimen_barcode": "SYNTHETIC-WRONG"}
    batch = LabImportBatch(source="manual", rows=[wrong, data])
    first, second = process_import_batch(db_session, batch, actor_id=actor.id)
    assert first.error_code == "specimen_mismatch"
    assert second.status == "saved"
    saved = db_session.scalar(
        select(LabReportValue).where(LabReportValue.instance_id == report.id)
    )
    assert saved.value_numeric == Decimal("0.01")
    assert (saved.result_payload or {}).get("comparator") == "lt"
    assert (saved.result_payload or {}).get("source_specimen_id") == specimen.id

    repeat = process_import_batch(
        db_session, LabImportBatch(source="manual", rows=[data]), actor_id=actor.id
    )
    assert repeat[0].status == "duplicate" and repeat[0].receipt_id == second.receipt_id
    different = {**data, "values": [{**data["values"][0], "value_text": "5"}]}
    conflict = process_import_batch(
        db_session, LabImportBatch(source="manual", rows=[different]), actor_id=actor.id
    )
    assert conflict[0].error_code == "message_conflict"
    whitespace = {
        **data,
        "message_id": str(uuid4()),
        "expected_updated_at": second.updated_at,
        "replace_existing": True,
        "values": [{**data["values"][0], "value_text": "   "}],
    }
    rejected = process_import_batch(
        db_session,
        LabImportBatch(source="manual", rows=[whitespace]),
        actor_id=actor.id,
    )
    assert rejected[0].error_code == "invalid_value"
    assert saved.value_numeric == Decimal("0.01")

    last_rejection = db_session.scalar(
        select(AuditLog)
        .where(AuditLog.event_type == "LAB_IMPORT_ROW_REJECTED")
        .order_by(AuditLog.id.desc())
        .limit(1)
    )
    assert last_rejection.actor_user_id == actor.id
    assert last_rejection.reason_code == {
        "source": "manual",
        "error_code": "invalid_value",
    }
    assert last_rejection.subject_patient_id is None and last_rejection.payload is None


@pytest.mark.unit
def test_csv_uses_the_published_catalog_mapping(db_session, test_patient):
    actor = synthetic_user(db_session, "Lab")
    service, old_report = synthetic_report(db_session, test_patient.id)
    draft = service.create_template_version(
        old_report.template_id, old_report.template_version_id
    )
    field = service._field_map(draft)["hgb"]
    field.analyte_code = "hgb"
    field.unit_code = "g_per_l"
    db_session.commit()
    published = service.publish_template_version(draft.id)
    report = service.create_instance(
        {
            "patient_id": test_patient.id,
            "template_id": old_report.template_id,
            "template_version_id": published.id,
        }
    )
    specimen = accepted_specimen(db_session, report, "SYNTHETIC-CSV")
    base = {
        "report_instance_id": report.id,
        "specimen_barcode": specimen.barcode,
    }
    cases = [
        (
            {
                **base,
                "values": [
                    {
                        "analyte_code": "unmapped",
                        "unit_code": "g_per_l",
                        "value_text": "0",
                    }
                ],
            },
            "unknown_analyte",
        ),
        (
            {
                **base,
                "values": [
                    {
                        "analyte_code": "hgb",
                        "unit_code": "mmol_per_l",
                        "value_text": "0",
                    }
                ],
            },
            "unit_mismatch",
        ),
        (
            {
                **base,
                "method_code": "unconfirmed",
                "values": [
                    {"analyte_code": "hgb", "unit_code": "g_per_l", "value_text": "0"}
                ],
            },
            "method_mismatch",
        ),
        (
            {
                **base,
                "values": [
                    {"analyte_code": "hgb", "unit_code": "g_per_l", "value_text": "0"}
                ],
            },
            None,
        ),
    ]
    rows = [{**case, "message_id": str(uuid4())} for case, _ in cases]
    preview = process_import_batch(
        db_session,
        LabImportBatch(source="csv", rows=rows),
        actor_id=actor.id,
        preview=True,
    )
    assert [item.error_code for item in preview] == [code for _, code in cases]
    assert preview[-1].status == "ready"
    rows[-1]["expected_updated_at"] = preview[-1].updated_at
    saved = process_import_batch(
        db_session,
        LabImportBatch(source="csv", rows=[rows[-1]]),
        actor_id=actor.id,
    )[0]
    assert saved.status == "saved"
    value = db_session.scalar(
        select(LabReportValue).where(LabReportValue.instance_id == report.id)
    )
    assert value.value_numeric == Decimal("0")
    assert value.result_payload["source_specimen_id"] == specimen.id


@pytest.mark.unit
def test_manual_import_rejects_aliases_of_the_same_field_in_preview_and_save(
    db_session, test_patient
):
    actor = synthetic_user(db_session, "Lab")
    service, old_report = synthetic_report(db_session, test_patient.id)
    draft = service.create_template_version(
        old_report.template_id, old_report.template_version_id
    )
    field = service._field_map(draft)["hgb"]
    field_key = "synthetic_hgb_slot"
    field.field_key = field_key
    field.analyte_code = "hgb"
    field.unit_code = "g_per_l"
    db_session.commit()
    published = service.publish_template_version(draft.id)
    report = service.create_instance(
        {
            "patient_id": test_patient.id,
            "template_id": old_report.template_id,
            "template_version_id": published.id,
        }
    )
    specimen = accepted_specimen(db_session, report, "SYNTHETIC-IMPORT-ALIAS")
    catalog_value = {"analyte_code": "hgb", "unit_code": "g_per_l", "value_text": "12"}
    field_value = {**catalog_value, "analyte_code": field_key, "value_text": "34"}
    valid_value = {**catalog_value, "value_text": "7"}
    rows = [
        {
            "message_id": str(uuid4()),
            "report_instance_id": report.id,
            "specimen_barcode": specimen.barcode,
            "values": values,
        }
        for values in (
            [catalog_value, field_value],
            [catalog_value, catalog_value],
            [valid_value],
        )
    ]
    expected_errors = ["duplicate_analyte", "duplicate_analyte", None]

    preview = process_import_batch(
        db_session,
        LabImportBatch(source="manual", rows=rows),
        actor_id=actor.id,
        preview=True,
    )
    assert [item.error_code for item in preview] == expected_errors
    assert preview[-1].status == "ready"
    assert db_session.scalar(select(LabImportReceipt.id)) is None

    for row in rows:
        row["expected_updated_at"] = preview[-1].updated_at
    saved = process_import_batch(
        db_session, LabImportBatch(source="manual", rows=rows), actor_id=actor.id
    )

    assert [item.error_code for item in saved] == expected_errors
    assert [item.status for item in saved] == ["error", "error", "saved"]
    receipt = db_session.scalars(select(LabImportReceipt)).one()
    assert receipt.message_id == rows[-1]["message_id"]
    value = db_session.scalars(
        select(LabReportValue).where(LabReportValue.instance_id == report.id)
    ).one()
    assert value.field_key == field_key
    assert value.value_numeric == Decimal("7")


@pytest.mark.unit
def test_critical_communication_inbox_is_separate_from_acknowledgment(
    db_session,
    test_patient,
    test_visit,
    monkeypatch,
):
    doctor = synthetic_user(db_session, "Doctor")
    profile = Doctor(user_id=doctor.id, specialty="cardiology", active=True)
    db_session.add(profile)
    db_session.flush()
    test_visit.doctor_id = profile.id
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(
        LabReportValue(
            field_key="hgb",
            value_numeric=Decimal("1"),
            evaluation_snapshot={"interpretation": "critical"},
        )
    )
    task = record_released_report(db_session, report)
    assert task is not None and task.recipient_user_id == doctor.id
    assert record_released_report(db_session, report).id == task.id
    db_session.commit()

    sender = AsyncMock(side_effect=[False, True])
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender
    )
    assert run(dispatch_pending(db_session)) == 0
    assert task.inbox_recorded_at is None
    task.next_attempt_at = datetime.now(UTC)
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 1
    assert task.state == "inbox_recorded"
    assert task.acknowledged_at is None
    assert sender.await_args.kwargs["entity_id"] == task.id
    assert "1" not in sender.await_args.kwargs["message"]

    with pytest.raises(LabReportingDomainError):
        acknowledge(db_session, task.id, actor_user_id=doctor.id + 1)
    db_session.rollback()
    now = acknowledge(db_session, task.id, actor_user_id=doctor.id).acknowledged_at
    assert (
        now is not None
        and acknowledge(db_session, task.id, actor_user_id=doctor.id).acknowledged_at
        == now
    )
    events = list(
        db_session.scalars(
            select(LabCriticalCommunicationEvent.event_type)
            .where(
                LabCriticalCommunicationEvent.communication_id == task.id,
            )
            .order_by(LabCriticalCommunicationEvent.id)
        )
    )
    assert events == [
        "created",
        "attempted",
        "delivery_failed",
        "attempted",
        "inbox_recorded",
        "acknowledged",
    ]


@pytest.mark.unit
def test_critical_admin_route_retries_and_never_replaces_clinical_acknowledgment(
    db_session, test_patient, test_visit, monkeypatch,
):
    admin = synthetic_user(db_session, "Admin")
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", admin.id)
    test_visit.doctor_id = None
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    assert task.state == "needs_assignment"
    assert task.recipient_user_id is None
    db_session.commit()

    sender = AsyncMock(side_effect=[False, True, True, True])
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session)) == 0
    assert sender.await_count == 1
    assert task.next_attempt_at is not None
    task.next_attempt_at = datetime.now(UTC)
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert task.state == "needs_assignment"
    assert task.inbox_recorded_at is None
    assert task.acknowledged_at is None
    for attempt in sender.await_args_list:
        sent = attempt.kwargs
        assert sent["recipient"].id == admin.id
        assert sent["entity_type"] == "lab_critical_assignment"
        assert sent["entity_id"] == task.id
        assert sent["metadata"] == {"communication_id": task.id}
        assert sent["deep_link"] == f"/lab?tab=operations&communication_id={task.id}"

    doctor = synthetic_user(db_session, "Doctor")
    profile = Doctor(user_id=doctor.id, specialty="cardiology", active=True)
    db_session.add(profile)
    db_session.flush()
    test_visit.doctor_id = profile.id
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 1
    assert task.state == "inbox_recorded"
    assert task.recipient_user_id == doctor.id
    assert sender.await_args.kwargs["recipient"].id == doctor.id

    escalate(db_session, task.id, actor_user_id=admin.id)
    assert run(dispatch_pending(db_session)) == 1
    assert task.state == "escalated"
    assert task.recipient_user_id == doctor.id
    assert sender.await_args.kwargs["recipient"].id == admin.id
    assert sender.await_args.kwargs["entity_type"] == "lab_critical_escalation"
    escalate(db_session, task.id, actor_user_id=admin.id)
    assert run(dispatch_pending(db_session)) == 0
    with pytest.raises(LabReportingDomainError):
        acknowledge(db_session, task.id, actor_user_id=admin.id)
    db_session.rollback()
    assert acknowledge(db_session, task.id, actor_user_id=doctor.id).state == "acknowledged"
    events = list(db_session.scalars(
        select(LabCriticalCommunicationEvent.event_type)
        .where(LabCriticalCommunicationEvent.communication_id == task.id)
        .order_by(LabCriticalCommunicationEvent.id)
    ))
    assert events.count("assignment_notified") == events.count("escalation_notified") == 1
    assert events.count("inbox_recorded") == events.count("acknowledged") == 1


@pytest.mark.unit
@pytest.mark.parametrize("escalated", [False, True])
def test_configured_critical_admin_recovers_existing_open_tasks(
    db_session, test_patient, test_visit, monkeypatch, escalated,
):
    admin = synthetic_user(db_session, "Admin")
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", None)
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", False)
    test_visit.doctor_id = None
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    db_session.commit()
    if escalated:
        escalate(db_session, task.id, actor_user_id=admin.id)
    assert task.next_attempt_at is None
    original_state = task.state

    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session)) == 0
    sender.assert_not_awaited()

    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", admin.id)
    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert task.state == original_state and task.next_attempt_at is None
    assert task.inbox_recorded_at is None and task.acknowledged_at is None
    sender.assert_awaited_once()
    args = sender.await_args.kwargs
    assert args["recipient"].id == admin.id
    assert args["entity_id"] == task.id
    assert args["entity_type"] == (
        "lab_critical_escalation" if escalated else "lab_critical_assignment"
    )


@pytest.mark.unit
@pytest.mark.parametrize(("role", "is_active", "shared_deployment"), [
    ("Doctor", True, False), ("Admin", False, False), ("Admin", True, True),
])
def test_critical_route_rejects_ineligible_configured_admin(
    db_session, test_patient, test_visit, monkeypatch, role, is_active, shared_deployment,
):
    configured_user = synthetic_user(db_session, role)
    configured_user.is_active = is_active
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", configured_user.id)
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", shared_deployment)
    test_visit.doctor_id = None
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    db_session.commit()

    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session)) == 0
    assert task.state == "needs_assignment"
    assert task.attempts == 0
    assert (task.next_attempt_at is None) == shared_deployment
    sender.assert_not_awaited()


@pytest.mark.unit
@pytest.mark.parametrize("admin_failure", ["inactive", "delivery_failed"])
@pytest.mark.parametrize("manual_assignment", [False, True])
def test_changed_doctor_is_not_blocked_by_unavailable_escalation_recipient(
    db_session, test_patient, test_visit, client, auth_headers, monkeypatch,
    admin_failure, manual_assignment,
):
    admin = synthetic_user(db_session, "Admin")
    doctors = [synthetic_user(db_session, "Doctor") for _ in range(2)]
    profiles = [Doctor(user_id=user.id, specialty="cardiology", active=True) for user in doctors]
    db_session.add_all(profiles)
    db_session.flush()
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", admin.id)
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", False)
    test_visit.doctor_id = profiles[0].id
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    db_session.commit()

    admin_available = [False]

    async def send(**kwargs):
        return kwargs["recipient"].id != admin.id or admin_available[0]

    sender = AsyncMock(side_effect=send)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session)) == 1
    assert task.state == "inbox_recorded"
    escalate(db_session, task.id, actor_user_id=admin.id)
    if admin_failure == "inactive":
        admin.is_active = False
    test_visit.doctor_id = profiles[1].id
    db_session.commit()
    route = "/api/v1/lab/critical-communications"
    if manual_assignment:
        assigned = client.post(f"{route}/{task.id}/assign", headers=auth_headers)
        assert assigned.status_code == 200
        assert assigned.json()["state"] == "escalated"
        repeated = client.post(f"{route}/{task.id}/assign", headers=auth_headers)
        assert repeated.status_code == 200
        assert repeated.json()["state"] == "escalated"

    assert run(dispatch_pending(db_session)) == 1
    assert task.state == "escalated" and task.recipient_user_id == doctors[1].id
    assert task.inbox_recorded_at is not None and task.acknowledged_at is None
    assert [call.kwargs["recipient"].id for call in sender.await_args_list].count(doctors[1].id) == 1
    response = client.get(route, params={"visit_id": test_visit.id}, headers=auth_headers)
    assert response.status_code == 200
    assert response.json()[0]["attempts"] == task.attempts + 1
    replay = client.post(f"{route}/{task.id}/escalate", headers=auth_headers)
    assert replay.status_code == 200
    assert replay.json()["attempts"] == task.attempts + 1
    with pytest.raises(LabReportingDomainError):
        acknowledge(db_session, task.id, actor_user_id=doctors[0].id)
    db_session.rollback()

    admin.is_active = True
    admin_available[0] = True
    task.next_attempt_at = datetime.now(UTC)
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert task.state == "escalated" and task.recipient_user_id == doctors[1].id
    assert [call.kwargs["recipient"].id for call in sender.await_args_list].count(doctors[1].id) == 1
    assert acknowledge(db_session, task.id, actor_user_id=doctors[1].id).state == "acknowledged"
    events = list(db_session.scalars(
        select(LabCriticalCommunicationEvent.event_type)
        .where(LabCriticalCommunicationEvent.communication_id == task.id)
        .order_by(LabCriticalCommunicationEvent.id)
    ))
    assert events.count("escalated") == events.count("escalation_notified") == 1
    assert events.count("inbox_recorded") == 2
    assert events.count("assigned") == 1


@pytest.mark.unit
def test_escalated_doctor_delivery_keeps_shared_tenant_admin_disabled(
    db_session, test_patient, test_visit, monkeypatch,
):
    admin = synthetic_user(db_session, "Admin")
    doctors = [synthetic_user(db_session, "Doctor") for _ in range(2)]
    profiles = [Doctor(user_id=user.id, specialty="cardiology", active=True) for user in doctors]
    db_session.add_all(profiles)
    db_session.flush()
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", admin.id)
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", True)
    test_visit.doctor_id = profiles[0].id
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    db_session.commit()
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session)) == 1
    escalate(db_session, task.id, actor_user_id=admin.id)
    test_visit.doctor_id = profiles[1].id
    db_session.commit()

    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert task.state == "escalated" and task.recipient_user_id == doctors[1].id
    assert [call.kwargs["recipient"].id for call in sender.await_args_list] == [
        doctors[0].id, doctors[1].id,
    ]
    assert acknowledge(db_session, task.id, actor_user_id=doctors[1].id).state == "acknowledged"


@pytest.mark.unit
def test_escalated_doctor_retries_do_not_starve_unattempted_tasks(
    db_session, test_patient, test_visit, monkeypatch,
):
    admin = synthetic_user(db_session, "Admin")
    doctor = synthetic_user(db_session, "Doctor")
    profile = Doctor(user_id=doctor.id, specialty="cardiology", active=True)
    db_session.add(profile)
    db_session.flush()
    test_visit.doctor_id = profile.id
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", None)
    tasks = []
    for _ in range(2):
        _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
        report.values.append(LabReportValue(
            field_key="hgb", value_numeric=Decimal("1"),
            evaluation_snapshot={"interpretation": "critical"},
        ))
        tasks.append(record_released_report(db_session, report))
    db_session.commit()
    for task in tasks:
        escalate(db_session, task.id, actor_user_id=admin.id)

    sender = AsyncMock(return_value=False)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session, limit=1)) == 0
    first_attempt = db_session.scalar(
        select(LabCriticalCommunicationEvent)
        .where(
            LabCriticalCommunicationEvent.communication_id == tasks[0].id,
            LabCriticalCommunicationEvent.event_type == "doctor_attempted",
        )
        .order_by(LabCriticalCommunicationEvent.id.desc())
    )
    first_attempt.occurred_at = datetime.now(UTC) - timedelta(minutes=2)
    db_session.commit()
    assert run(dispatch_pending(db_session, limit=1)) == 0
    assert [call.kwargs["entity_id"] for call in sender.await_args_list] == [
        tasks[0].id, tasks[1].id,
    ]


@pytest.mark.unit
def test_escalated_doctor_delivery_retries_without_duplicate_attempts(
    db_session, test_patient, test_visit, monkeypatch,
):
    admin = synthetic_user(db_session, "Admin")
    doctors = [synthetic_user(db_session, "Doctor") for _ in range(2)]
    profiles = [Doctor(user_id=user.id, specialty="cardiology", active=True) for user in doctors]
    db_session.add_all(profiles)
    db_session.flush()
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", admin.id)
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", False)
    test_visit.doctor_id = profiles[0].id
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    db_session.commit()

    doctor_available = [False]

    async def send(**kwargs):
        return kwargs["recipient"].id != doctors[1].id or doctor_available[0]

    sender = AsyncMock(side_effect=send)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session)) == 1
    escalate(db_session, task.id, actor_user_id=admin.id)
    admin.is_active = False
    test_visit.doctor_id = profiles[1].id
    db_session.commit()

    assert run(dispatch_pending(db_session)) == 0
    assert run(dispatch_pending(db_session)) == 0
    assert task.state == "escalated" and task.recipient_user_id == doctors[1].id
    assert task.inbox_recorded_at is None
    assert [call.kwargs["recipient"].id for call in sender.await_args_list].count(doctors[1].id) == 1

    attempt = db_session.scalar(
        select(LabCriticalCommunicationEvent)
        .where(
            LabCriticalCommunicationEvent.communication_id == task.id,
            LabCriticalCommunicationEvent.event_type == "doctor_attempted",
        )
        .order_by(LabCriticalCommunicationEvent.id.desc())
    )
    attempt.occurred_at = datetime.now(UTC) - timedelta(minutes=2)
    doctor_available[0] = True
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert task.inbox_recorded_at is not None and task.acknowledged_at is None
    assert [call.kwargs["recipient"].id for call in sender.await_args_list].count(doctors[1].id) == 2
    assert acknowledge(db_session, task.id, actor_user_id=doctors[1].id).state == "acknowledged"


@pytest.mark.unit
def test_escalation_reaches_admin_when_changed_doctor_delivery_fails(
    db_session, test_patient, test_visit, monkeypatch,
):
    admin = synthetic_user(db_session, "Admin")
    doctors = [synthetic_user(db_session, "Doctor") for _ in range(2)]
    profiles = [Doctor(user_id=user.id, specialty="cardiology", active=True) for user in doctors]
    db_session.add_all(profiles)
    db_session.flush()
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", admin.id)
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", False)
    test_visit.doctor_id = profiles[0].id
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    db_session.commit()
    escalate(db_session, task.id, actor_user_id=admin.id)
    test_visit.doctor_id = profiles[1].id
    db_session.commit()

    sender = AsyncMock(side_effect=[False, True, True])
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session, limit=1)) == 0
    assert sender.await_count == 1
    assert run(dispatch_pending(db_session, limit=1)) == 1
    assert task.state == "escalated" and task.recipient_user_id == doctors[1].id
    assert task.inbox_recorded_at is None
    attempt = db_session.scalar(
        select(LabCriticalCommunicationEvent)
        .where(
            LabCriticalCommunicationEvent.communication_id == task.id,
            LabCriticalCommunicationEvent.event_type == "doctor_attempted",
        )
        .order_by(LabCriticalCommunicationEvent.id.desc())
    )
    attempt.occurred_at = datetime.now(UTC) - timedelta(minutes=2)
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert task.state == "escalated" and task.recipient_user_id == doctors[1].id
    assert task.inbox_recorded_at is not None
    assert [call.kwargs["recipient"].id for call in sender.await_args_list] == [
        doctors[1].id, admin.id, doctors[1].id,
    ]
    assert [call.kwargs["entity_type"] for call in sender.await_args_list] == [
        "lab_critical_communication", "lab_critical_escalation", "lab_critical_communication",
    ]


@pytest.mark.unit
@pytest.mark.parametrize("change", ["replaced", "assigned", "removed"])
def test_escalated_critical_task_follows_changed_visit_doctor(
    db_session, test_patient, test_visit, monkeypatch, change,
):
    admin = synthetic_user(db_session, "Admin")
    doctors = [synthetic_user(db_session, "Doctor") for _ in range(2)]
    profiles = [Doctor(user_id=user.id, specialty="cardiology", active=True) for user in doctors]
    db_session.add_all(profiles)
    db_session.flush()
    monkeypatch.setattr(settings, "LAB_CRITICAL_ESCALATION_ADMIN_ID", admin.id)
    monkeypatch.setattr(settings, "TENANT_SCOPE_ENFORCE_WRITES", False)
    test_visit.doctor_id = None if change == "assigned" else profiles[0].id
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(LabReportValue(
        field_key="hgb", value_numeric=Decimal("1"),
        evaluation_snapshot={"interpretation": "critical"},
    ))
    task = record_released_report(db_session, report)
    db_session.commit()
    escalate(db_session, task.id, actor_user_id=admin.id)

    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender,
    )
    assert run(dispatch_pending(db_session)) == (1 if change == "assigned" else 2)
    assert sender.await_args.kwargs["entity_type"] == "lab_critical_escalation"
    assert task.state == "escalated"

    test_visit.doctor_id = None if change == "removed" else profiles[1].id
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert task.acknowledged_at is None
    if change == "removed":
        assert task.state == "needs_assignment" and task.recipient_user_id is None
        assert sender.await_args.kwargs["recipient"].id == admin.id
        assert sender.await_args.kwargs["entity_type"] == "lab_critical_assignment"
    else:
        assert task.state == "escalated" and task.recipient_user_id == doctors[1].id
        assert sender.await_args.kwargs["recipient"].id == doctors[1].id
        with pytest.raises(LabReportingDomainError):
            acknowledge(db_session, task.id, actor_user_id=doctors[0].id)
        db_session.rollback()
        assert acknowledge(db_session, task.id, actor_user_id=doctors[1].id).state == "acknowledged"

    events = list(db_session.scalars(
        select(LabCriticalCommunicationEvent.event_type)
        .where(LabCriticalCommunicationEvent.communication_id == task.id)
        .order_by(LabCriticalCommunicationEvent.id)
    ))
    assert events.count("escalated") == 1
    assert events.count("escalation_notified") == 1
    assert events.count("needs_assignment" if change == "removed" else "assigned") == 1


@pytest.mark.unit
def test_recorded_critical_task_follows_current_doctor(
    db_session,
    test_patient,
    test_visit,
    client,
    auth_headers,
    monkeypatch,
):
    doctors = [synthetic_user(db_session, "Doctor") for _ in range(2)]
    profiles = [
        Doctor(user_id=user.id, specialty="cardiology", active=True) for user in doctors
    ]
    db_session.add_all(profiles)
    db_session.flush()
    test_visit.doctor_id = profiles[0].id
    _, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.values.append(
        LabReportValue(
            field_key="hgb",
            value_numeric=Decimal("1"),
            evaluation_snapshot={"interpretation": "critical"},
        )
    )
    task = record_released_report(db_session, report)
    assert task is not None
    task_id = task.id
    visit_id = test_visit.id
    db_session.commit()

    def doctor_headers(user):
        token = authentication_service.create_access_token(
            {
                "sub": str(user.id),
                "username": user.username,
                "role": user.role,
                "is_active": user.is_active,
                "is_superuser": user.is_superuser,
            }
        )
        return {"Authorization": f"Bearer {token}"}

    route = "/api/v1/lab/critical-communications"
    params = {"visit_id": visit_id}
    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender
    )
    assert run(dispatch_pending(db_session)) == 1
    assert task.state == "inbox_recorded"
    before = client.get(route, params=params, headers=doctor_headers(doctors[0]))
    assert before.status_code == 200
    assert before.json()[0]["available_actions"] == ["acknowledge"]
    assert before.json()[0]["attempts"] == 1
    admin = client.get(route, params=params, headers=auth_headers)
    assert admin.status_code == 200
    assert "assign" in admin.json()[0]["available_actions"]

    test_visit.doctor_id = profiles[1].id
    db_session.commit()
    stale = client.post(
        f"{route}/{task_id}/acknowledge", headers=doctor_headers(doctors[0])
    )
    assert stale.status_code == 404
    assert (
        client.get(route, params=params, headers=doctor_headers(doctors[0])).status_code
        == 403
    )

    assert run(dispatch_pending(db_session)) == 1
    assert task.recipient_user_id == doctors[1].id
    assert task.state == "inbox_recorded"
    assert [call.kwargs["recipient"].id for call in sender.await_args_list] == [
        user.id for user in doctors
    ]
    after = client.get(route, params=params, headers=doctor_headers(doctors[1]))
    assert after.status_code == 200
    assert after.json()[0]["id"] == task_id
    assert after.json()[0]["available_actions"] == ["acknowledge"]
    assert after.json()[0]["attempts"] == 2

    locked_sql = []
    scalar = db_session.scalar

    def capture_scalar(statement, *args, **kwargs):
        locked_sql.append(str(statement.compile(dialect=postgresql.dialect())))
        return scalar(statement, *args, **kwargs)

    with monkeypatch.context() as capture:
        capture.setattr(db_session, "scalar", capture_scalar)
        acknowledged_task = acknowledge(
            db_session, task_id, actor_user_id=doctors[1].id
        )
        assert acknowledged_task.state == "acknowledged"
    assert any("FOR SHARE OF visits, doctors, users" in sql for sql in locked_sql)

    test_visit.doctor_id = profiles[0].id
    db_session.commit()
    assert run(dispatch_pending(db_session)) == 0
    assert len(sender.await_args_list) == 2
    events = list(
        db_session.scalars(
            select(LabCriticalCommunicationEvent.event_type)
            .where(LabCriticalCommunicationEvent.communication_id == task_id)
            .order_by(LabCriticalCommunicationEvent.id)
        )
    )
    assert events == [
        "created",
        "attempted",
        "inbox_recorded",
        "assigned",
        "attempted",
        "inbox_recorded",
        "acknowledged",
    ]


@pytest.mark.unit
def test_critical_release_without_doctor_remains_accessible_and_correction_has_own_task(
    db_session, test_patient, test_visit, client, auth_headers, monkeypatch
):
    test_visit.doctor_id = None
    service, report = synthetic_report(db_session, test_patient.id, visit_id=test_visit.id)
    report.status = "FINALIZED"
    report.finalized_at = datetime.now(UTC)
    report.values.append(
        LabReportValue(
            field_key="hgb",
            value_numeric=Decimal("1"),
            evaluation_snapshot={
                "status": "evaluated",
                "interpretation": "critical",
                "visible": True,
            },
        )
    )
    task = record_released_report(db_session, report)
    assert task is not None and task.state == "needs_assignment"
    assert task.recipient_user_id is None
    assert report.order.status != "completed"
    db_session.commit()

    sender = AsyncMock(return_value=True)
    monkeypatch.setattr(
        notification_sender_service, "send_canonical_notification_to_user", sender
    )
    assert run(dispatch_pending(db_session)) == 0
    sender.assert_not_awaited()

    route = "/api/v1/lab/critical-communications"
    listed = client.get(route, params={"visit_id": test_visit.id}, headers=auth_headers)
    assert listed.status_code == 200
    assert [(item["id"], item["state"]) for item in listed.json()] == [
        (task.id, "needs_assignment"),
    ]
    published_pdf = client.get(
        f"/api/v1/lab/report-instances/{report.id}/pdf", headers=auth_headers,
    )
    assert published_pdf.status_code == 200
    assert published_pdf.headers["content-disposition"] == (
        f'inline; filename="lab-report-{report.id}.pdf"'
    )
    assert published_pdf.content.startswith(b"%PDF")

    rejected_assignment = client.post(f"{route}/{task.id}/assign", headers=auth_headers)
    assert rejected_assignment.status_code == 409
    first_escalation = client.post(f"{route}/{task.id}/escalate", headers=auth_headers)
    repeated_escalation = client.post(f"{route}/{task.id}/escalate", headers=auth_headers)
    assert first_escalation.status_code == repeated_escalation.status_code == 200
    assert first_escalation.json()["state"] == "escalated"
    assert first_escalation.json()["escalated_at"] == repeated_escalation.json()["escalated_at"]
    sender.assert_not_awaited()

    doctor = synthetic_user(db_session, "Doctor")
    profile = Doctor(user_id=doctor.id, specialty="cardiology", active=True)
    db_session.add(profile)
    db_session.flush()
    test_visit.doctor_id = profile.id
    db_session.commit()
    assigned = client.post(f"{route}/{task.id}/assign", headers=auth_headers)
    assert assigned.status_code == 200 and assigned.json()["state"] == "escalated"
    assert run(dispatch_pending(db_session)) == 1
    assert task.state == "escalated" and task.acknowledged_at is None
    assert task.inbox_recorded_at is not None

    revision = service.revise(report.id)
    revision.values[0].evaluation_snapshot = {
        "status": "evaluated",
        "interpretation": "normal",
        "visible": True,
    }
    revision.status = "FINALIZED"
    revision.finalized_at = datetime.now(UTC)
    corrected_task = record_released_report(db_session, revision)
    assert corrected_task is not None and corrected_task.report_instance_id == revision.id
    assert corrected_task.id != task.id
    assert corrected_task.supersedes_communication_id == task.id
    assert corrected_task.field_keys == []
    assert task.state == "superseded"
    assert report.values[0].evaluation_snapshot["interpretation"] == "critical"
    db_session.commit()

    assert run(dispatch_pending(db_session)) == 1
    assert run(dispatch_pending(db_session)) == 0
    assert [call.kwargs["entity_id"] for call in sender.await_args_list] == [
        task.id,
        corrected_task.id,
    ]
    assert sender.await_args.kwargs["title"] == "Исправлен критический лабораторный результат"
    assert corrected_task.acknowledged_at is None

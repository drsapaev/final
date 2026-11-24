from asyncio import run
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.clinic import Doctor
from app.models.lab import LabOrder, LabReportValue
from app.models.lab_critical_communication import LabCriticalCommunicationEvent
from app.models.lab_import import LabImportReceipt
from app.models.lab_specimen import LabSpecimen, LabSpecimenAssignment
from app.models.user import User
from app.schemas.lab_import import LabImportBatch
from app.services.lab_critical_communication import (
    acknowledge,
    dispatch_pending,
    record_released_report,
)
from app.services.lab_import import process_import_batch
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


@pytest.mark.unit
def test_import_validation_receipt_and_partial_retry(db_session, test_patient):
    actor = synthetic_user(db_session, "Lab")
    service, report = synthetic_report(db_session, test_patient.id)
    specimen = LabSpecimen(
        order_id=report.order_id,
        barcode="SYNTHETIC-IMPORT",
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

    repeat = process_import_batch(
        db_session, LabImportBatch(source="manual", rows=[data]), actor_id=actor.id
    )
    assert repeat[0].status == "duplicate" and repeat[0].receipt_id == second.receipt_id
    different = {**data, "values": [{**data["values"][0], "value_text": "5"}]}
    conflict = process_import_batch(
        db_session, LabImportBatch(source="manual", rows=[different]), actor_id=actor.id
    )
    assert conflict[0].error_code == "message_conflict"


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

"""Issue the existing Prescription from a persisted EMR revision."""

from collections.abc import Callable
from datetime import UTC
from hashlib import sha256
from json import dumps

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.crud.emr import prescription
from app.models.appointment import Appointment
from app.models.emr import Prescription
from app.models.emr_v2 import EMRRecord, EMRRevision
from app.models.visit import Visit
from app.repositories.canonical_visit_repository import CanonicalVisitRepository
from app.schemas.emr import MedicationItem
from app.schemas.emr_workspace import ReviewedPrescriptionText, WorkspacePrescription
from app.services.emr_workspace_service import WorkspaceError


def _legacy_prescription_for_visit(
    db: Session, visit: Visit, *, for_update: bool,
) -> Prescription | None:
    candidates = (
        db.query(Prescription, Appointment)
        .join(Appointment, Prescription.appointment_id == Appointment.id)
        .filter(
            Prescription.visit_id.is_(None),
            Appointment.patient_id == visit.patient_id,
            Appointment.doctor_id == visit.doctor_id,
            Appointment.appointment_date == visit.visit_date,
        )
        .populate_existing()
    )
    resolver = CanonicalVisitRepository(db)
    match = None
    for item, appointment in candidates.all():
        visits = resolver.list_visits_for_appointment(appointment)
        if not any(candidate.id == visit.id for candidate in visits):
            continue
        if len(visits) != 1 or match is not None:
            raise WorkspaceError(409, "PRESCRIPTION_LEGACY_AMBIGUOUS")
        match = item
    if match is not None and for_update:
        # Queue pairing can lock an appointment before its visit. Do not wait
        # for it while holding the visit lock. The issuer can reload and retry.
        appointment = (
            db.query(Appointment)
            .filter(
                Appointment.id == match.appointment_id,
                Appointment.patient_id == visit.patient_id,
            )
            .populate_existing()
            .with_for_update(of=Appointment, skip_locked=True)
            .one_or_none()
        )
        if appointment is None:
            raise WorkspaceError(409, "PRESCRIPTION_TEXT_REVIEW_REQUIRED")
        visits = resolver.list_visits_for_appointment(appointment)
        if len(visits) != 1 or visits[0].id != visit.id:
            raise WorkspaceError(409, "PRESCRIPTION_LEGACY_AMBIGUOUS")
        match = (
            db.query(Prescription)
            .filter(
                Prescription.id == match.id,
                Prescription.appointment_id == appointment.id,
                Prescription.visit_id.is_(None),
            )
            .populate_existing()
            .with_for_update(of=Prescription)
            .one_or_none()
        )
        if match is None:
            raise WorkspaceError(409, "PRESCRIPTION_TEXT_REVIEW_REQUIRED")
    return match


def _prescription_for_visit(
    db: Session, visit: Visit, *, for_update: bool = False,
) -> Prescription | None:
    linked = (
        db.query(Prescription)
        .join(Visit, Visit.id == Prescription.visit_id)
        .filter(Visit.id == visit.id, Visit.patient_id == visit.patient_id)
        .populate_existing()
    )
    if for_update:
        linked = linked.with_for_update(of=Prescription)
    linked_items = linked.order_by(Prescription.id).limit(2).all()
    if len(linked_items) > 1:
        # The shared writer must be able to select the exact row being reviewed.
        raise WorkspaceError(409, "PRESCRIPTION_LEGACY_AMBIGUOUS")
    item = linked_items[0] if linked_items else _legacy_prescription_for_visit(
        db, visit, for_update=for_update,
    )
    if item is None:
        return None
    if item.emr_record_id is not None:
        record_id = db.query(EMRRecord.id).filter_by(
            id=item.emr_record_id, visit_id=visit.id, patient_id=visit.patient_id,
        ).scalar()
        if record_id is None:
            code = (
                "PRESCRIPTION_LEGACY_AMBIGUOUS"
                if item.visit_id is None
                else "PATIENT_CONTEXT_CHANGED"
            )
            raise WorkspaceError(409, code)
    if item.visit_id is not None and item.appointment_id is not None:
        appointment_id = db.query(Appointment.id).filter_by(
            id=item.appointment_id, patient_id=visit.patient_id,
        ).scalar()
        if appointment_id is None:
            raise WorkspaceError(409, "PATIENT_CONTEXT_CHANGED")
    return item


def _text_review_token(item: Prescription | None) -> str | None:
    if item is None or not (
        (item.instructions or "").strip() or (item.doctor_notes or "").strip()
    ):
        return None
    updated_at = item.updated_at
    if updated_at is not None:
        updated_at = (
            updated_at.astimezone(UTC)
            if updated_at.tzinfo
            else updated_at.replace(tzinfo=UTC)
        )
    payload = dumps((
        item.id, item.instructions, item.doctor_notes,
        updated_at.isoformat() if updated_at is not None else None,
    ))
    return sha256(payload.encode()).hexdigest()


def _prescription_response(
    item: Prescription, visit_id: int, revision_version: int | None,
) -> WorkspacePrescription:
    return WorkspacePrescription(
        id=item.id,
        visit_id=visit_id,
        emr_version=revision_version,
        is_draft=item.is_draft,
        instructions=item.instructions,
        doctor_notes=item.doctor_notes,
        review_token=_text_review_token(item),
    )


def read_prescription(db: Session, visit: Visit) -> WorkspacePrescription | None:
    item = _prescription_for_visit(db, visit)
    if item is None:
        return None
    revision_version = (
        db.query(EMRRevision.version)
        .join(EMRRecord, EMRRevision.emr_id == EMRRecord.id)
        .filter(
            EMRRevision.id == item.emr_revision_id,
            EMRRecord.id == item.emr_record_id,
            EMRRecord.visit_id == visit.id,
            EMRRecord.patient_id == visit.patient_id,
        )
        .scalar()
        if item.emr_revision_id is not None
        else None
    )
    return _prescription_response(item, visit.id, revision_version)


def prescription_medications(data: dict) -> list[dict]:
    medications = data.get("medications")
    raw = medications.get("list") if isinstance(medications, dict) else medications
    if not isinstance(raw, list) or not raw or len(raw) > 100:
        raise WorkspaceError(422, "PRESCRIPTION_MEDICATIONS_REQUIRED")

    result = []
    for row in raw:
        if not isinstance(row, dict):
            raise WorkspaceError(422, "PRESCRIPTION_MEDICATIONS_INCOMPLETE")
        values = {
            "name": row.get("name", row.get("drug")),
            "dosage": row.get("dose", row.get("dosage")),
            "frequency": row.get("frequency", row.get("freq")),
            "duration": row.get("duration"),
            "instructions": row.get("instructions") or row.get("note"),
            "quantity": row.get("quantity"),
        }
        if any(
            not isinstance(values[key], str) or not values[key].strip()
            for key in ("name", "dosage", "frequency", "duration")
        ) or isinstance(values["quantity"], bool):
            raise WorkspaceError(422, "PRESCRIPTION_MEDICATIONS_INCOMPLETE")
        try:
            result.append(MedicationItem.model_validate(values).model_dump())
        except ValidationError:
            raise WorkspaceError(422, "PRESCRIPTION_MEDICATIONS_INCOMPLETE") from None
    return result


def issue_prescription(
    db: Session,
    visit: Visit,
    expected_row_version: int,
    *,
    authorize_visit: Callable[[int], None],
    reviewed_text: ReviewedPrescriptionText | None = None,
) -> WorkspacePrescription:
    # Lock in the same order as the shared upsert: visit, then source record.
    expected_patient_id = visit.patient_id
    locked_visit = (
        db.query(Visit)
        .filter(Visit.id == visit.id)
        .populate_existing()
        .with_for_update(of=Visit)
        .one_or_none()
    )
    if locked_visit is None:
        raise WorkspaceError(404, "VISIT_NOT_FOUND")
    authorize_visit(locked_visit.id)
    if locked_visit.patient_id != expected_patient_id:
        raise WorkspaceError(409, "PATIENT_CONTEXT_CHANGED")
    if locked_visit.status == "canceled":
        raise WorkspaceError(409, "VISIT_CANCELED")
    record = (
        db.query(EMRRecord)
        .filter_by(
            visit_id=locked_visit.id, patient_id=expected_patient_id, is_active=True
        )
        .populate_existing()
        .with_for_update()
        .one_or_none()
    )
    if (
        record is None
        or record.status == "draft"
        or record.row_version != expected_row_version
    ):
        raise WorkspaceError(409, "PRESCRIPTION_STALE_EMR")
    revision = (
        db.query(EMRRevision)
        .filter_by(emr_id=record.id, version=record.version)
        .one_or_none()
    )
    if revision is None:
        raise WorkspaceError(409, "PRESCRIPTION_STALE_EMR")
    current = _prescription_for_visit(db, locked_visit, for_update=True)
    submitted_token = reviewed_text.expected_token if reviewed_text is not None else None
    if submitted_token != _text_review_token(current):
        raise WorkspaceError(409, "PRESCRIPTION_TEXT_REVIEW_REQUIRED")

    values = {"medications": prescription_medications(revision.data), "is_draft": False}
    if reviewed_text is not None and current is not None:
        values.update(
            instructions=reviewed_text.instructions, doctor_notes=reviewed_text.doctor_notes,
        )
        current_text = (current.instructions, current.doctor_notes)
        if current.emr_revision_id == revision.id and current_text != (
            reviewed_text.instructions, reviewed_text.doctor_notes,
        ):
            # The rollback trigger invalidates attribution if content changes
            # without changing the source ID. Reassign it in the same transaction.
            current.emr_revision_id = None
            db.flush()
    item = prescription.store_for_visit(
        db,
        visit_id=locked_visit.id,
        emr_record_id=record.id,
        emr_revision_id=revision.id,
        legacy_item=current if current is not None and current.visit_id is None else None,
        values=values,
    )
    return _prescription_response(item, locked_visit.id, revision.version)

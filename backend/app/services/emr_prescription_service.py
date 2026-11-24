"""Issue the existing Prescription from a persisted EMR revision."""

from collections.abc import Callable

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.crud.emr import prescription
from app.models.appointment import Appointment
from app.models.emr import Prescription
from app.models.emr_v2 import EMRRecord, EMRRevision
from app.models.visit import Visit
from app.repositories.canonical_visit_repository import CanonicalVisitRepository
from app.schemas.emr import MedicationItem
from app.schemas.emr_workspace import WorkspacePrescription
from app.services.emr_workspace_service import WorkspaceError


def _legacy_prescription_for_visit(db: Session, visit: Visit) -> Prescription | None:
    candidates = (
        db.query(Prescription, Appointment)
        .join(Appointment, Prescription.appointment_id == Appointment.id)
        .filter(
            Prescription.visit_id.is_(None),
            Appointment.patient_id == visit.patient_id,
            Appointment.doctor_id == visit.doctor_id,
            Appointment.appointment_date == visit.visit_date,
        )
        .all()
    )
    resolver = CanonicalVisitRepository(db)
    match = None
    for item, appointment in candidates:
        visits = resolver.list_visits_for_appointment(appointment)
        if not any(candidate.id == visit.id for candidate in visits):
            continue
        if len(visits) != 1 or match is not None:
            raise WorkspaceError(409, "PRESCRIPTION_LEGACY_AMBIGUOUS")
        if item.emr_record_id is not None:
            record = db.get(EMRRecord, item.emr_record_id)
            if record is None or (record.visit_id, record.patient_id) != (
                visit.id, visit.patient_id
            ):
                raise WorkspaceError(409, "PRESCRIPTION_LEGACY_AMBIGUOUS")
        match = item
    return match


def read_prescription(db: Session, visit: Visit) -> WorkspacePrescription | None:
    item = prescription.get_by_visit(db, visit_id=visit.id) or (
        _legacy_prescription_for_visit(db, visit)
    )
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
    return WorkspacePrescription(
        id=item.id,
        visit_id=visit.id,
        emr_version=revision_version,
        is_draft=item.is_draft,
    )


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
    legacy_item = (
        _legacy_prescription_for_visit(db, locked_visit)
        if prescription.get_by_visit(db, visit_id=locked_visit.id) is None
        else None
    )
    item = prescription.store_for_visit(
        db,
        visit_id=locked_visit.id,
        emr_record_id=record.id,
        emr_revision_id=revision.id,
        legacy_item=legacy_item,
        values={
            "medications": prescription_medications(revision.data),
            "is_draft": False,
        },
    )
    return WorkspacePrescription(
        id=item.id,
        visit_id=locked_visit.id,
        emr_version=revision.version,
        is_draft=item.is_draft,
    )

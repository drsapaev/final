"""Issue the existing Prescription from a persisted EMR revision."""

from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.crud.emr import prescription
from app.models.emr_v2 import EMRRecord, EMRRevision
from app.models.visit import Visit
from app.schemas.emr import MedicationItem
from app.schemas.emr_workspace import WorkspacePrescription
from app.services.emr_workspace_service import WorkspaceError


def read_prescription(db: Session, visit: Visit) -> WorkspacePrescription | None:
    item = prescription.get_by_visit(db, visit_id=visit.id)
    if item is None:
        return None
    revision = (
        db.get(EMRRevision, item.emr_revision_id)
        if item.emr_revision_id is not None
        else None
    )
    return WorkspacePrescription(
        id=item.id,
        visit_id=visit.id,
        emr_version=revision.version if revision else None,
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
    db: Session, visit: Visit, expected_row_version: int
) -> WorkspacePrescription:
    # Lock in the same order as the shared upsert: visit, then source record.
    db.query(Visit.id).filter(Visit.id == visit.id).with_for_update().one()
    record = (
        db.query(EMRRecord)
        .filter_by(visit_id=visit.id, patient_id=visit.patient_id, is_active=True)
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
    item = prescription.store_for_visit(
        db,
        visit_id=visit.id,
        emr_record_id=record.id,
        emr_revision_id=revision.id,
        values={
            "medications": prescription_medications(revision.data),
            "is_draft": False,
        },
    )
    return WorkspacePrescription(
        id=item.id,
        visit_id=visit.id,
        emr_version=revision.version,
        is_draft=item.is_draft,
    )

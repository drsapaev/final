"""Patient facts and signed visit history for the EMR workspace."""

from collections.abc import Callable
from datetime import UTC, datetime
from json import dumps
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.emr_v2 import EMRRecord
from app.models.patient import Patient
from app.models.patient_clinical import PatientClinicalRevision
from app.models.visit import Visit
from app.repositories.emr_workspace_repository import EMRWorkspaceRepository
from app.schemas.emr_workspace import (
    AllergyState,
    ClinicalEntryOut,
    ClinicalEntryWrite,
    FollowUpWrite,
    TransferredField,
    WorkspaceHistoryDocument,
    WorkspaceHistoryItem,
    WorkspaceLabComparison,
    WorkspaceLabValue,
    WorkspaceOut,
    WorkspacePatient,
    WorkspaceVisit,
)
from app.services.emr_contract import get_emr_text_field
from app.services.emr_lab_result_evidence import frozen_assessment, released_numeric_observation
from app.services.emr_v2_service import EMRPatientContextMismatch, emr_v2_service


class WorkspaceError(Exception):
    def __init__(self, status_code: int, code: str):
        self.status_code = status_code
        self.code = code


def prepare_workspace_document(
    db: Session,
    visit_id: int,
    data: dict,
    previous: EMRRecord | None,
    actor_id: int,
    authorize_source: Callable[[int], None],
) -> dict:
    stored_value = previous.data.get("follow_up") if previous else None
    stored = stored_value if isinstance(stored_value, dict) else {}
    if "follow_up" not in data:
        return {**data, "follow_up": stored_value} if stored_value is not None else data

    try:
        request = FollowUpWrite.model_validate(data["follow_up"])
    except ValidationError:
        raise WorkspaceError(422, "INVALID_FOLLOW_UP") from None

    def key(source: dict) -> tuple:
        return tuple(
            source.get(field)
            for field in (
                "source_visit_id",
                "source_version",
                "field",
                "confirmed_current",
            )
        )

    retained = {}
    prior_transfers = stored.get("transferred_fields")
    for item in prior_transfers if isinstance(prior_transfers, list) else []:
        try:
            prior = TransferredField.model_validate(item)
        except ValidationError:
            continue
        retained[key(prior.model_dump())] = prior
    selections = (
        request.transferred_fields
        if "transferred_fields" in request.model_fields_set
        else list(retained.values())
    )
    service = EMRWorkspaceService(db)
    verified: dict[tuple, dict] = {}
    source_documents: dict[tuple[int, int], WorkspaceHistoryDocument] = {}
    for selection in selections:
        marker = key(selection.model_dump())
        if marker in retained:
            verified[marker] = retained[marker].model_dump(mode="json")
            continue
        visit, patient = service.context(visit_id, None)
        source_key = (selection.source_visit_id, selection.source_version)
        source = source_documents.get(source_key)
        if source is None:
            authorize_source(selection.source_visit_id)
            source = service.history_document(visit, *source_key)
            source_documents[source_key] = source
        text = getattr(source, selection.field)
        if not text.strip():
            raise WorkspaceError(422, "TRANSFER_SOURCE_FIELD_EMPTY")
        verified[marker] = TransferredField(
            **selection.model_dump(),
            source_patient_id=patient.id,
            source_document_id=source.id,
            text=text,
            transferred_by=actor_id,
            transferred_at=datetime.now(UTC),
        ).model_dump(mode="json")
    follow_up = {
        **stored,
        **request.model_dump(exclude_unset=True),
        "transferred_fields": list(verified.values()),
    }
    return {**data, "follow_up": follow_up}


def get_allergy_state(entries: list[PatientClinicalRevision]) -> AllergyState:
    for entry in entries:
        fact = entry.clinical_details
        if fact["kind"] == "allergy" and fact["status"] == "active":
            return "specific"
    for entry in entries:
        fact = entry.clinical_details
        if fact["kind"] == "allergy_check":
            return fact["status"]
    return "not_checked"


def summarize_history(
    record: EMRRecord, visit: Visit, data: dict, version: int
) -> WorkspaceHistoryItem:
    specialty = data.get("specialty_data")
    echo = specialty.get("echo") if isinstance(specialty, dict) else None
    vitals = data.get("vitals")
    return WorkspaceHistoryItem(
        id=record.id,
        visit_id=visit.id,
        visit_date=visit.visit_date,
        version=version,
        status=record.status,
        signed_at=record.signed_at,
        complaints=get_emr_text_field(data, "complaints"),
        diagnosis=get_emr_text_field(data, "diagnosis"),
        treatment=get_emr_text_field(data, "treatment"),
        recommendations=get_emr_text_field(data, "recommendations"),
        vitals=vitals if isinstance(vitals, dict) else {},
        echo=echo if isinstance(echo, dict) else {},
    )


class EMRWorkspaceService:
    def __init__(self, db: Session):
        self.db = db
        self.repository = EMRWorkspaceRepository(db)

    def context(
        self, visit_id: int, expected_patient_id: int | None
    ) -> tuple[Visit, Patient]:
        context = self.repository.visit_and_patient(visit_id)
        if context is None:
            raise WorkspaceError(404, "VISIT_NOT_FOUND")
        visit, patient = context
        if expected_patient_id is not None and patient.id != expected_patient_id:
            raise WorkspaceError(409, "PATIENT_CONTEXT_CHANGED")
        return visit, patient

    def read(
        self,
        visit: Visit,
        patient: Patient,
        doctor_id: int | None,
        offset: int,
        limit: int,
    ) -> WorkspaceOut:
        entries = self.repository.current_entries(patient.id)
        history = self.repository.prior_documents(visit, doctor_id, limit + 1, offset)
        history_items = [
            summarize_history(record, source_visit, record.data, record.version)
            for record, source_visit in history[:limit]
        ]
        current_lab_values: list[WorkspaceLabValue] = []
        labs_by_visit = {
            visit.id: current_lab_values,
            **{item.visit_id: item.laboratory for item in history_items},
        }
        for row in self.repository.workspace_lab_values(patient.id, list(labs_by_visit)):
            value = row["value"]
            snapshot = row["evaluation_snapshot"]
            if not isinstance(snapshot, dict):
                snapshot = {}
            unit = snapshot.get("unit", row["unit"])
            if unit is not None and not isinstance(unit, str):
                unit = row["unit"]
                snapshot = {}
            status, interpretation, abnormal = frozen_assessment(snapshot, value)
            observation = released_numeric_observation(
                value, row["result_payload"], snapshot, row["value_numeric"]
            )
            comparison = None
            if (
                observation is not None
                and row["released_at"] is not None
                and row["test_code"]
            ):
                comparison = WorkspaceLabComparison(
                    key=dumps(
                        (row["template_version_id"], row["test_code"], *observation.context)
                    ),
                    field_key=row["test_code"],
                    template_name=row["template_name"],
                    template_version=row["template_version"],
                    value=format(observation.value, "f"),
                    observed_on=observation.observed_on,
                )
            labs_by_visit[row["source_visit_id"]].append(
                WorkspaceLabValue(
                    instance_id=row["source_instance_id"],
                    name=row["test_name"],
                    value=value,
                    unit=unit,
                    finalized_at=row["released_at"],
                    abnormal=abnormal,
                    evaluation_status=status,
                    interpretation=interpretation,
                    comparison=comparison,
                )
            )
        return WorkspaceOut(
            patient=WorkspacePatient(
                id=patient.id,
                full_name=patient.full_name,
                birth_date=patient.birth_date,
                legacy_allergies=patient.allergies,
                legacy_conditions=patient.chronic_conditions,
            ),
            visit=WorkspaceVisit(
                id=visit.id, date=visit.visit_date, status=visit.status
            ),
            allergy_state=get_allergy_state(entries),
            clinical_entries=[
                ClinicalEntryOut.model_validate(entry) for entry in entries
            ],
            history=history_items,
            has_more_history=len(history) > limit,
            current_laboratory=current_lab_values,
        )

    def history_document(
        self, visit: Visit, source_visit_id: int, version: int
    ) -> WorkspaceHistoryDocument:
        source, _ = self.context(source_visit_id, visit.patient_id)
        if source.id == visit.id or (
            visit.visit_date
            and source.visit_date
            and source.visit_date > visit.visit_date
        ):
            raise WorkspaceError(404, "HISTORY_DOCUMENT_NOT_FOUND")
        try:
            record = emr_v2_service.get_by_visit(self.db, source.id)
        except EMRPatientContextMismatch:
            raise WorkspaceError(404, "HISTORY_DOCUMENT_NOT_FOUND") from None
        if record is None or record.patient_id != visit.patient_id:
            raise WorkspaceError(404, "HISTORY_DOCUMENT_NOT_FOUND")
        revision = emr_v2_service.get_revision(self.db, record.id, version)
        if revision is None or revision.change_type not in {"signed", "amended"}:
            raise WorkspaceError(404, "HISTORY_DOCUMENT_NOT_FOUND")
        summary = summarize_history(record, source, revision.data, revision.version)
        summary.status = revision.change_type
        return WorkspaceHistoryDocument(**summary.model_dump(), data=revision.data)

    def update(
        self, visit: Visit, entry_id: UUID, payload: ClinicalEntryWrite, author_id: int
    ) -> ClinicalEntryOut:
        if payload.source == "legacy_verified" and not payload.confirmed:
            raise WorkspaceError(422, "LEGACY_REQUIRES_CONFIRMATION")
        self.repository.lock_patient(visit.patient_id)
        entries = self.repository.current_entries(visit.patient_id)
        previous = next(
            (entry for entry in entries if entry.entry_id == entry_id), None
        )
        current_version = previous.version if previous else 0
        if payload.expected_version != current_version or (
            previous is None and self.repository.entry_exists(entry_id)
        ):
            raise WorkspaceError(409, "CLINICAL_ENTRY_CONFLICT")

        details = payload.clinical_details.model_dump()
        if previous and previous.clinical_details["kind"] != details["kind"]:
            raise WorkspaceError(409, "CLINICAL_ENTRY_KIND_CHANGED")
        if details["kind"] == "allergy_check":
            if any(
                entry.clinical_details["kind"] == "allergy_check"
                and entry.entry_id != entry_id
                for entry in entries
            ):
                raise WorkspaceError(409, "ALLERGY_CHECK_EXISTS")
            if (
                details["status"] == "none_reported"
                and get_allergy_state(entries) == "specific"
            ):
                raise WorkspaceError(409, "ACTIVE_ALLERGY_EXISTS")

        now = datetime.now(UTC)
        row = PatientClinicalRevision(
            entry_id=entry_id,
            version=current_version + 1,
            patient_id=visit.patient_id,
            visit_id=visit.id,
            author_id=author_id,
            source=payload.source,
            clinical_details=details,
            recorded_at=now,
            confirmed_at=now
            if payload.confirmed
            else (
                previous.confirmed_at
                if previous
                and previous.clinical_details == details
                and previous.source == payload.source
                else None
            ),
        )
        try:
            self.repository.add_entry(row)
        except IntegrityError as exc:
            self.db.rollback()
            raise WorkspaceError(409, "CLINICAL_ENTRY_CONFLICT") from exc
        return ClinicalEntryOut.model_validate(row)

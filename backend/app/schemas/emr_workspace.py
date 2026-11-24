"""Contracts for the visit-scoped workspace and longitudinal clinical data."""

import re
from datetime import UTC, date, datetime
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

NamedClinicalValue = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)
]
ClinicalSource = Literal["clinician", "patient_report", "legacy_verified"]
TransferField = Literal["complaints", "diagnosis", "treatment", "recommendations"]
AllergyState = Literal["specific", "none_reported", "unknown", "not_checked"]


class DatedClinicalFact(BaseModel):
    # ISO calendar date, month or year. Missing parts are not inferred.
    event_on: str | None = None
    ended_on: str | None = None

    @field_validator("event_on", "ended_on")
    @classmethod
    def accept_partial_date(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not re.fullmatch(r"\d{4}(?:-\d{2}(?:-\d{2})?)?", value):
            raise ValueError("Use YYYY, YYYY-MM or YYYY-MM-DD")
        date.fromisoformat(value + {4: "-01-01", 7: "-01", 10: ""}[len(value)])
        return value


class ProblemFact(DatedClinicalFact):
    kind: Literal["problem"]
    name: NamedClinicalValue
    code: str | None = Field(None, max_length=32)
    status: Literal["active", "resolved", "inactive"]


class MedicationFact(DatedClinicalFact):
    kind: Literal["medication"]
    name: NamedClinicalValue
    dose: str | None = Field(None, max_length=120)
    regimen: str | None = Field(None, max_length=240)
    status: Literal["prescribed", "reported", "taking", "stopped"]


class AllergyFact(DatedClinicalFact):
    kind: Literal["allergy"]
    name: NamedClinicalValue
    reaction: str | None = Field(None, max_length=240)
    severity: Literal["mild", "moderate", "severe"] | None = None
    status: Literal["active", "inactive"]


class AllergyCheckFact(DatedClinicalFact):
    kind: Literal["allergy_check"]
    status: Literal["none_reported", "unknown", "not_checked"]


ClinicalFact = Annotated[
    ProblemFact | MedicationFact | AllergyFact | AllergyCheckFact,
    Field(discriminator="kind"),
]


class ClinicalEntryWrite(BaseModel):
    patient_id: int = Field(gt=0)
    expected_version: int = Field(ge=0)
    source: ClinicalSource
    confirmed: bool = False
    clinical_details: ClinicalFact


class ClinicalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    entry_id: UUID
    version: int
    schema_version: int
    visit_id: int
    author_id: int
    source: ClinicalSource
    clinical_details: ClinicalFact
    recorded_at: datetime
    confirmed_at: datetime | None


class WorkspacePatient(BaseModel):
    id: int
    full_name: str
    birth_date: date | None
    legacy_allergies: str | None
    legacy_conditions: str | None


class WorkspaceVisit(BaseModel):
    id: int
    date: date | None
    status: str


class WorkspaceLabComparison(BaseModel):
    key: str = Field(description="Opaque key for an exact template version, field and unit")
    field_key: str
    template_name: str
    template_version: int
    value: str = Field(description="Persisted numeric value from the source lab report")


class WorkspaceLabValue(BaseModel):
    instance_id: int
    name: str
    value: str
    unit: str | None
    finalized_at: datetime | None
    abnormal: bool
    comparison: WorkspaceLabComparison | None = None


class WorkspaceHistoryItem(BaseModel):
    id: int
    visit_id: int
    visit_date: date | None
    version: int
    status: str
    signed_at: datetime | None
    complaints: str
    diagnosis: str
    treatment: str
    recommendations: str
    vitals: dict[str, Any]
    echo: dict[str, Any]
    laboratory: list[WorkspaceLabValue] = Field(default_factory=list)


class WorkspaceHistoryDocument(WorkspaceHistoryItem):
    data: dict[str, Any]


class WorkspaceOut(BaseModel):
    patient: WorkspacePatient
    visit: WorkspaceVisit
    allergy_state: AllergyState
    clinical_entries: list[ClinicalEntryOut]
    history: list[WorkspaceHistoryItem]
    has_more_history: bool
    current_laboratory: list[WorkspaceLabValue] = Field(default_factory=list)


class TransferSelection(BaseModel):
    source_visit_id: int = Field(gt=0)
    source_version: int = Field(gt=0)
    field: TransferField
    confirmed_current: bool = False


class TransferredField(TransferSelection):
    source_patient_id: int
    source_document_id: int
    text: str
    transferred_by: int
    transferred_at: datetime


class FollowUpWrite(BaseModel):
    model_config = ConfigDict(extra="allow")

    mode: Literal["initial", "follow_up", "new_complaint"] | None = None
    changes: str | None = Field(None, max_length=5000)
    actual_treatment: str | None = Field(None, max_length=5000)
    prior_plan_follow_through: str | None = Field(None, max_length=5000)
    new_results: str | None = Field(None, max_length=5000)
    transferred_fields: list[TransferSelection] = Field(
        default_factory=list, max_length=24
    )


class IssuePrescription(BaseModel):
    patient_id: int = Field(gt=0)
    expected_row_version: int = Field(gt=0)


class WorkspacePrescription(BaseModel):
    id: int
    visit_id: int
    emr_version: int | None
    is_draft: bool


class LabReviewRequest(BaseModel):
    patient_id: int = Field(gt=0)
    next_action: str | None = Field(None, max_length=500)


class LabReviewOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    reviewer_id: int
    reviewed_at: datetime
    next_action: str | None

    @field_validator("reviewed_at")
    @classmethod
    def normalize_review_time(cls, value: datetime) -> datetime:
        return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class WorkspaceLabReport(BaseModel):
    id: int
    status: str
    template_name: str
    supersedes_instance_id: int | None
    finalized_at: datetime | None
    is_current_final: bool
    reviews: list[LabReviewOut]


class WorkspaceLabOrder(BaseModel):
    id: int
    status: str
    created_at: datetime
    reports: list[WorkspaceLabReport]


class WorkspaceExecution(BaseModel):
    id: int
    service_name: str
    attempt: int
    status: str


class WorkspaceInvoiceStatus(BaseModel):
    id: int
    status: str


class WorkspaceLabs(BaseModel):
    orders: list[WorkspaceLabOrder]
    unlinked_reports: list[WorkspaceLabReport]
    executions: list[WorkspaceExecution]
    invoices: list[WorkspaceInvoiceStatus]

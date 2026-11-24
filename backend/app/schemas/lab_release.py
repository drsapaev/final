"""Commands and read models for managed laboratory report release."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

LabQCStatus = Literal["accepted", "rejected", "not_applicable"]


class LabReportVersionCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_updated_at: str = Field(min_length=19, max_length=50)


class LabReportReasonCommand(LabReportVersionCommand):
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def trim_reason(cls, value: str) -> str:
        return value.strip() if isinstance(value, str) else value


class LabReportQCIn(LabReportVersionCommand):
    status: LabQCStatus
    reason: str | None = Field(default=None, max_length=1000)
    method: str | None = Field(default=None, max_length=100)
    instrument_ref: str | None = Field(default=None, max_length=100)
    series_ref: str | None = Field(default=None, max_length=100)

    @field_validator("reason", "method", "instrument_ref", "series_ref", mode="before")
    @classmethod
    def trim_text(cls, value: str | None) -> str | None:
        return value.strip() or None if isinstance(value, str) else value

    @model_validator(mode="after")
    def require_qc_evidence(self) -> "LabReportQCIn":
        if self.status in {"not_applicable", "rejected"} and not self.reason:
            raise ValueError("Provide the reason for the QC disposition")
        if self.status != "not_applicable" and not (self.method and self.series_ref):
            raise ValueError("Provide the QC method and series reference")
        return self


class LabQCEvidenceOut(BaseModel):
    status: LabQCStatus
    method: str | None = None
    instrument_ref: str | None = None
    series_ref: str | None = None


class LabReleaseSpecimenOut(BaseModel):
    id: int
    status: str
    revision: int


class LabReportWorkflowEvidenceOut(BaseModel):
    specimens: list[LabReleaseSpecimenOut] | None = None
    qc_event_id: int | None = None
    review_event_id: int | None = None
    qc: LabQCEvidenceOut | None = None


class LabReportWorkflowEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    kind: Literal[
        "entered",
        "submitted",
        "reviewed",
        "returned",
        "qc_recorded",
        "finalized",
        "revision_created",
    ]
    actor_user_id: int
    actor_name: str
    occurred_at: datetime
    report_version: datetime
    reason: str | None = None
    evidence: LabReportWorkflowEvidenceOut | None = None

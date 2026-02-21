"""
EMR v2 Schemas - Pydantic models for API
"""

from datetime import datetime
from typing import Any

from pydantic import Field
from pydantic import ConfigDict

from app.schemas.base import ORMModel

# =============================================================================
# EMR Data Structures
# =============================================================================


class DiagnosisData(ORMModel):
    """Diagnosis structure within EMR data"""

    main: str = Field(default="", max_length=500)
    icd10_code: str | None = Field(default=None, max_length=16)
    secondary: list[dict[str, str]] = Field(default_factory=list)


class VitalsData(ORMModel):
    """Vital signs structure"""

    blood_pressure: dict[str, int] | None = None  # {"systolic": 120, "diastolic": 80}
    pulse: int | None = Field(default=None, ge=0, le=300)
    spo2: int | None = Field(default=None, ge=0, le=100)
    height: int | None = Field(default=None, ge=0, le=300)
    weight: float | None = Field(default=None, ge=0, le=500)
    temperature: float | None = Field(default=None, ge=30, le=45)


class PlanData(ORMModel):
    """Treatment plan structure"""

    examinations: list[str] = Field(default_factory=list)
    treatment: str = Field(default="", max_length=5000)
    consultations: list[str] = Field(default_factory=list)


class EMRDataSchema(ORMModel):
    """
    Complete EMR clinical data structure.
    Stored in JSONB `data` field.
    """

    complaints: str = Field(default="", max_length=5000)
    anamnesis_morbi: str = Field(default="", max_length=5000)
    anamnesis_vitae: str = Field(default="", max_length=5000)
    examination: str = Field(default="", max_length=10000)
    diagnosis: DiagnosisData = Field(default_factory=DiagnosisData)
    vitals: VitalsData = Field(default_factory=VitalsData)
    plan: PlanData = Field(default_factory=PlanData)
    recommendations: str = Field(default="", max_length=5000)
    specialty_data: dict[str, Any] = Field(
        default_factory=dict, description="Specialty-specific fields"
    )


# =============================================================================
# EMR Record Schemas
# =============================================================================


class EMRRecordBase(ORMModel):
    """Base EMR record schema"""

    pass


class EMRRecordCreate(EMRRecordBase):
    """Schema for creating EMR (internal use)"""

    patient_id: int
    visit_id: int
    data: dict[str, Any] = Field(default_factory=dict)
    created_by: int


class EMRSaveRequest(ORMModel):
    """
    Schema for saving EMR (API request).
    Includes optimistic locking fields.
    """

    data: dict[str, Any] = Field(..., description="Complete EMR clinical data")
    row_version: int = Field(
        default=0, description="Current row version for optimistic locking"
    )
    client_session_id: str | None = Field(
        default=None,
        max_length=64,
        description="Client session UUID for conflict resolution",
    )
    is_draft: bool = Field(default=True, description="Save as draft or finalize")


class EMRSignRequest(ORMModel):
    """Schema for signing EMR"""

    data: dict[str, Any] = Field(..., description="Final EMR data")
    row_version: int = Field(..., description="Current row version")
    client_session_id: str | None = None


class EMRAmendRequest(ORMModel):
    """Schema for amending signed EMR"""

    data: dict[str, Any] = Field(..., description="Amended EMR data")
    reason: str = Field(
        ..., min_length=10, max_length=1000, description="Reason for amendment (required)"
    )
    row_version: int = Field(..., description="Current row version")


class EMRRestoreRequest(ORMModel):
    """Schema for restoring to specific version"""

    target_version: int = Field(..., ge=1, description="Version to restore to")
    reason: str | None = Field(
        default=None, max_length=1000, description="Reason for restore"
    )


class EMRRecordOut(ORMModel):
    """Schema for EMR output"""

    id: int
    patient_id: int
    visit_id: int
    version: int
    row_version: int
    data: dict[str, Any]
    diagnosis_main: str | None = None
    icd10_code: str | None = None
    status: str
    created_at: datetime
    created_by: int
    updated_at: datetime | None = None
    updated_by: int | None = None
    signed_at: datetime | None = None
    signed_by: int | None = None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class EMRRecordSummary(ORMModel):
    """Brief EMR summary for lists"""

    id: int
    visit_id: int
    version: int
    status: str
    diagnosis_main: str | None = None
    icd10_code: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    signed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


# =============================================================================
# EMR Revision Schemas
# =============================================================================


class EMRRevisionOut(ORMModel):
    """Schema for revision output"""

    id: int
    emr_id: int
    version: int
    data: dict[str, Any]  # DB column name
    change_type: str
    change_summary: str | None = None
    created_by: int  # DB column name
    created_at: datetime  # DB column name
    client_session_id: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EMRRevisionSummary(ORMModel):
    """Brief revision summary for history list"""

    id: int
    version: int
    change_type: str
    change_summary: str | None = None
    created_by: int  # DB column name
    created_at: datetime  # DB column name

    model_config = ConfigDict(from_attributes=True)


class EMRHistoryOut(ORMModel):
    """Schema for EMR history response"""

    emr_id: int
    current_version: int
    revisions: list[EMRRevisionSummary]


# =============================================================================
# EMR Diff Schemas
# =============================================================================


class FieldChange(ORMModel):
    """Single field change in diff"""

    field: str
    change_type: str  # added | removed | modified
    old_value: Any | None = None
    new_value: Any | None = None


class EMRDiffOut(ORMModel):
    """Schema for version comparison"""

    emr_id: int
    version_from: int
    version_to: int
    changes: list[FieldChange]
    summary: str  # "3 fields changed"


# =============================================================================
# EMR Conflict Schema
# =============================================================================


class EMRConflictError(ORMModel):
    """Schema for conflict error response"""

    error: str = "CONFLICT"
    message: str = "EMR was modified by another user"
    current_version: int
    your_version: int
    last_edited_by: int
    last_edited_at: datetime


# =============================================================================
# EMR Audit Schemas
# =============================================================================


class EMRAuditLogOut(ORMModel):
    """Schema for audit log output"""

    id: int
    emr_id: int
    patient_id: int
    visit_id: int
    action: str
    user_id: int
    user_role: str
    ip_address: str | None = None
    extra_data: dict[str, Any] | None = None
    timestamp: datetime

    model_config = ConfigDict(from_attributes=True)

"""
EMR v2 Schemas - Pydantic models for API
"""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import Field, field_validator

from app.schemas.base import ORMModel


# =============================================================================
# EMR Data Structures
# =============================================================================


class DiagnosisData(ORMModel):
    """Diagnosis structure within EMR data"""

    main: str = Field(default="", max_length=500)
    icd10_code: Optional[str] = Field(default=None, max_length=16)
    secondary: List[Dict[str, str]] = Field(default_factory=list)


class VitalsData(ORMModel):
    """Vital signs structure"""

    blood_pressure: Optional[Dict[str, int]] = None  # {"systolic": 120, "diastolic": 80}
    pulse: Optional[int] = Field(default=None, ge=0, le=300)
    spo2: Optional[int] = Field(default=None, ge=0, le=100)
    height: Optional[int] = Field(default=None, ge=0, le=300)
    weight: Optional[float] = Field(default=None, ge=0, le=500)
    temperature: Optional[float] = Field(default=None, ge=30, le=45)


class PlanData(ORMModel):
    """Treatment plan structure"""

    examinations: List[str] = Field(default_factory=list)
    treatment: str = Field(default="", max_length=5000)
    consultations: List[str] = Field(default_factory=list)


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
    specialty_data: Dict[str, Any] = Field(
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
    data: Dict[str, Any] = Field(default_factory=dict)
    created_by: int


class EMRSaveRequest(ORMModel):
    """
    Schema for saving EMR (API request).
    Includes optimistic locking fields.
    """

    data: Dict[str, Any] = Field(..., description="Complete EMR clinical data")
    row_version: int = Field(
        default=0, description="Current row version for optimistic locking"
    )
    client_session_id: Optional[str] = Field(
        default=None,
        max_length=64,
        description="Client session UUID for conflict resolution",
    )
    is_draft: bool = Field(default=True, description="Save as draft or finalize")


class EMRSignRequest(ORMModel):
    """Schema for signing EMR"""

    data: Dict[str, Any] = Field(..., description="Final EMR data")
    row_version: int = Field(..., description="Current row version")
    client_session_id: Optional[str] = None


class EMRAmendRequest(ORMModel):
    """Schema for amending signed EMR"""

    data: Dict[str, Any] = Field(..., description="Amended EMR data")
    reason: str = Field(
        ..., min_length=10, max_length=1000, description="Reason for amendment (required)"
    )
    row_version: int = Field(..., description="Current row version")


class EMRRestoreRequest(ORMModel):
    """Schema for restoring to specific version"""

    target_version: int = Field(..., ge=1, description="Version to restore to")
    reason: Optional[str] = Field(
        default=None, max_length=1000, description="Reason for restore"
    )


class EMRRecordOut(ORMModel):
    """Schema for EMR output"""

    id: int
    patient_id: int
    visit_id: int
    version: int
    row_version: int
    data: Dict[str, Any]
    diagnosis_main: Optional[str] = None
    icd10_code: Optional[str] = None
    status: str
    created_at: datetime
    created_by: int
    updated_at: Optional[datetime] = None
    updated_by: Optional[int] = None
    signed_at: Optional[datetime] = None
    signed_by: Optional[int] = None
    is_active: bool

    class Config:
        from_attributes = True


class EMRRecordSummary(ORMModel):
    """Brief EMR summary for lists"""

    id: int
    visit_id: int
    version: int
    status: str
    diagnosis_main: Optional[str] = None
    icd10_code: Optional[str] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    signed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# =============================================================================
# EMR Revision Schemas
# =============================================================================


class EMRRevisionOut(ORMModel):
    """Schema for revision output"""

    id: int
    emr_id: int
    version: int
    data: Dict[str, Any]  # DB column name
    change_type: str
    change_summary: Optional[str] = None
    created_by: int  # DB column name
    created_at: datetime  # DB column name
    client_session_id: Optional[str] = None

    class Config:
        from_attributes = True


class EMRRevisionSummary(ORMModel):
    """Brief revision summary for history list"""

    id: int
    version: int
    change_type: str
    change_summary: Optional[str] = None
    created_by: int  # DB column name
    created_at: datetime  # DB column name

    class Config:
        from_attributes = True


class EMRHistoryOut(ORMModel):
    """Schema for EMR history response"""

    emr_id: int
    current_version: int
    revisions: List[EMRRevisionSummary]


# =============================================================================
# EMR Diff Schemas
# =============================================================================


class FieldChange(ORMModel):
    """Single field change in diff"""

    field: str
    change_type: str  # added | removed | modified
    old_value: Optional[Any] = None
    new_value: Optional[Any] = None


class EMRDiffOut(ORMModel):
    """Schema for version comparison"""

    emr_id: int
    version_from: int
    version_to: int
    changes: List[FieldChange]
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
    ip_address: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None
    timestamp: datetime

    class Config:
        from_attributes = True

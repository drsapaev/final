"""Pydantic schemas for dental clinical endpoints.

P0-8 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `examination_data: dict[str, Any]`,
`treatment_data: dict[str, Any]`, and `prosthetic_data: dict[str, Any]`
with no validation, allowing clinical record corruption via mass-assignment.
These schemas enforce explicit field types and constraints based on the
frontend DentistPanelUnified.jsx form structure.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

# =============================================================================
# DENTAL EXAMINATION
# =============================================================================


class DentalExaminationRequest(BaseModel):
    """Request body for POST /dental/examinations.

    Based on frontend DentistPanelUnified.jsx examinationForm:
    patient_id, examination_date, oral_hygiene, caries_status,
    periodontal_status, occlusion, missing_teeth, dental_plaque,
    gingival_bleeding, diagnosis, recommendations.
    """

    patient_id: int = Field(..., ge=1, description="Patient ID")
    examination_date: str = Field(..., max_length=50, description="Examination date (YYYY-MM-DD or DD.MM.YYYY)")
    oral_hygiene: str = Field("", max_length=500, description="Oral hygiene assessment")
    caries_status: str = Field("", max_length=500, description="Caries status description")
    periodontal_status: str = Field("", max_length=500, description="Periodontal status")
    occlusion: str = Field("", max_length=500, description="Occlusion assessment")
    missing_teeth: str = Field("", max_length=500, description="Missing teeth list")
    dental_plaque: str = Field("", max_length=500, description="Dental plaque assessment")
    gingival_bleeding: str = Field("", max_length=500, description="Gingival bleeding assessment")
    diagnosis: str = Field("", max_length=2000, description="Diagnosis text")
    recommendations: str = Field("", max_length=2000, description="Recommendations")

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("examination data must be a JSON object")
        if len(data) > 50:
            raise ValueError("too many fields (max 50)")
        return data


# =============================================================================
# DENTAL TREATMENT PLAN
# =============================================================================


class DentalTreatmentRequest(BaseModel):
    """Request body for POST /dental/treatments.

    Treatment plan data for dental procedures.
    """

    patient_id: int = Field(..., ge=1, description="Patient ID")
    treatment_date: str = Field(..., max_length=50, description="Treatment date")
    tooth_number: str | None = Field(None, max_length=20, description="Tooth number(s) treated")
    treatment_type: str = Field("", max_length=200, description="Type of treatment")
    description: str = Field("", max_length=2000, description="Treatment description")
    cost: float | None = Field(None, ge=0, description="Treatment cost")
    status: str = Field("planned", max_length=50, description="Treatment status")
    notes: str = Field("", max_length=2000, description="Additional notes")

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("treatment data must be a JSON object")
        if len(data) > 50:
            raise ValueError("too many fields (max 50)")
        return data


# =============================================================================
# DENTAL PROSTHETIC
# =============================================================================


class DentalProstheticRequest(BaseModel):
    """Request body for POST /dental/prosthetics.

    Prosthetic/denture record data.
    """

    patient_id: int = Field(..., ge=1, description="Patient ID")
    prosthetic_date: str = Field(..., max_length=50, description="Prosthetic procedure date")
    prosthetic_type: str = Field("", max_length=200, description="Type of prosthetic (crown, bridge, denture, etc.)")
    tooth_number: str | None = Field(None, max_length=20, description="Tooth number(s) involved")
    material: str = Field("", max_length=200, description="Material used")
    description: str = Field("", max_length=2000, description="Procedure description")
    cost: float | None = Field(None, ge=0, description="Prosthetic cost")
    status: str = Field("planned", max_length=50, description="Prosthetic status")
    notes: str = Field("", max_length=2000, description="Additional notes")

    model_config = {"extra": "forbid"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("prosthetic data must be a JSON object")
        if len(data) > 50:
            raise ValueError("too many fields (max 50)")
        return data


__all__ = [
    "DentalExaminationRequest",
    "DentalTreatmentRequest",
    "DentalProstheticRequest",
]

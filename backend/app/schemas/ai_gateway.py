"""Pydantic schemas for AI gateway and AI integration endpoints.

P0-5 FIX (ENDPOINT-VALIDATION-AUDIT):
Previously these endpoints accepted `request: dict[str, Any]` with no
validation, allowing prompt injection, mass-assignment, and schema drift.
These schemas enforce explicit field types and constraints.

All schemas use snake_case to match the existing backend API contract.
Frontend uses a mix of snake_case (patient_age, patient_gender) and
camelCase (patientAge, patientGender) — for backward compatibility,
we accept both via Pydantic aliases where needed.
"""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


# =============================================================================
# SHARED COMPONENTS
# =============================================================================


class LabResultItem(BaseModel):
    """Single lab result item (used by /interpret-lab endpoints)."""

    name: str | None = Field(None, description="Test name (e.g. 'Гемоглобин')")
    parameter: str | None = Field(None, description="Alt field for test name (used by /interpret-lab-results)")
    value: float | str | None = Field(None, description="Test value (numeric or text)")
    unit: str | None = Field(None, description="Unit of measurement")
    reference: str | None = Field(None, description="Reference range text (e.g. '130-160')")


# =============================================================================
# AI GATEWAY REQUESTS (ai_gateway.py)
# =============================================================================


class AnalyzeComplaintsRequest(BaseModel):
    """Request body for POST /ai/analyze-complaints.

    Frontend sends: { complaint, patient_age, patient_gender, specialty, provider? }
    """

    complaint: str = Field(..., min_length=1, max_length=10000, description="Patient complaint text")
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] | None = Field(None, description="Patient gender")
    specialty: str | None = Field(None, max_length=100, description="Medical specialty hint (e.g. 'general', 'cardiology')")
    language: Literal["ru", "uz", "en"] = Field("ru", description="Response language")
    provider: str | None = Field(None, max_length=50, description="AI provider hint (openai, gemini, deepseek)")

    @field_validator("complaint")
    @classmethod
    def _strip_complaint(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("complaint must not be empty")
        return v


class SuggestICD10Request(BaseModel):
    """Request body for POST /ai/suggest-icd10."""

    symptoms: list[str] | None = Field(None, description="List of symptom strings")
    diagnosis: str | None = Field(None, max_length=5000, description="Working diagnosis text")
    specialty: str | None = Field(None, max_length=100, description="Medical specialty hint")
    language: Literal["ru", "uz", "en"] = Field("ru", description="Response language")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("symptoms")
    @classmethod
    def _validate_symptoms(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return None
        cleaned = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        if not cleaned:
            return None
        if len(cleaned) > 50:
            raise ValueError("too many symptoms (max 50)")
        return cleaned


class DifferentialDiagnosisRequest(BaseModel):
    """Request body for POST /ai/differential-diagnosis."""

    symptoms: list[str] = Field(..., min_length=1, max_length=50, description="List of symptom strings")
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] | None = Field(None, description="Patient gender")
    specialty: str | None = Field(None, max_length=100, description="Medical specialty hint")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("symptoms")
    @classmethod
    def _validate_symptoms(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        if not cleaned:
            raise ValueError("symptoms must contain at least one non-empty string")
        return cleaned


class InterpretLabRequest(BaseModel):
    """Request body for POST /ai/interpret-lab (gateway version).

    Accepts a list of lab result items + patient context.
    """

    results: list[LabResultItem] = Field(..., min_length=1, max_length=200, description="Lab result items")
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] | None = Field(None, description="Patient gender")
    specialty: str | None = Field(None, max_length=100, description="Medical specialty hint")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")


class AnalyzeSkinRequest(BaseModel):
    """Request body for POST /ai/analyze-skin."""

    image_data: str = Field(..., min_length=1, max_length=10_000_000, description="Base64-encoded image data")
    metadata: dict[str, Any] | None = Field(
        None,
        description="Optional metadata: location, duration, changes, etc.",
    )
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] | None = Field(None, description="Patient gender")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("metadata")
    @classmethod
    def _validate_metadata_size(cls, v: dict[str, Any] | None) -> dict[str, Any] | None:
        if v is None:
            return None
        if len(v) > 20:
            raise ValueError("metadata must not contain more than 20 keys")
        return v


class AnalyzeECGRequest(BaseModel):
    """Request body for POST /ai/analyze-ecg."""

    ecg_data: dict[str, Any] = Field(
        ...,
        description="ECG measurements: heart_rate, rhythm, intervals, etc.",
    )
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] | None = Field(None, description="Patient gender")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("ecg_data")
    @classmethod
    def _validate_ecg_data_size(cls, v: dict[str, Any]) -> dict[str, Any]:
        if not v:
            raise ValueError("ecg_data must not be empty")
        if len(v) > 50:
            raise ValueError("ecg_data must not contain more than 50 keys")
        return v


class SymptomCheckRequest(BaseModel):
    """Request body for POST /ai/symptom-check (triage, limited analysis)."""

    symptoms: list[str] = Field(..., min_length=1, max_length=50, description="List of symptom strings")
    duration: str | None = Field(None, max_length=200, description="Duration of symptoms (free text)")
    severity: Literal["mild", "moderate", "severe", "very_severe"] | None = Field(
        None, description="Severity level"
    )
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] | None = Field(None, description="Patient gender")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("symptoms")
    @classmethod
    def _validate_symptoms(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        if not cleaned:
            raise ValueError("symptoms must contain at least one non-empty string")
        return cleaned


class AnalyzeDocumentRequest(BaseModel):
    """Request body for POST /ai/analyze-document."""

    document_text: str = Field(..., min_length=1, max_length=50_000, description="Medical document text")
    document_type: Literal[
        "medical_report",
        "ultrasound_report",
        "ct_report",
        "mri_report",
        "xray_report",
        "lab_results",
        "discharge_summary",
        "consultation_note",
        "other",
    ] = Field("medical_report", description="Document type for AI context")
    specialty: str | None = Field(None, max_length=100, description="Medical specialty hint")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("document_text")
    @classmethod
    def _strip_document_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("document_text must not be empty")
        return v


class DrugInteractionRequest(BaseModel):
    """Request body for POST /ai/drug-interaction."""

    medications: list[str] = Field(..., min_length=1, max_length=50, description="List of medication names")
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] | None = Field(None, description="Patient gender")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("medications")
    @classmethod
    def _validate_medications(cls, v: list[str]) -> list[str]:
        cleaned = [m.strip() for m in v if isinstance(m, str) and m.strip()]
        if not cleaned:
            raise ValueError("medications must contain at least one non-empty name")
        return cleaned


# =============================================================================
# AI INTEGRATION REQUESTS (ai_integration.py)
# =============================================================================


class AnalyzeComplaintsIntegrationRequest(BaseModel):
    """Request body for POST /ai-integration/analyze-complaints (legacy integration).

    Frontend (useEMRAI.js) sends: { complaints, specialty, language, provider? }
    """

    complaints: str = Field(..., min_length=1, max_length=10000, description="Patient complaints text")
    complaint: str | None = Field(None, max_length=10000, description="Alt field for complaint text (single)")
    specialty: str = Field("general", max_length=100, description="Medical specialty hint")
    language: Literal["ru", "uz", "en"] = Field("ru", description="Response language")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("complaints")
    @classmethod
    def _strip_complaints(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("complaints must not be empty")
        return v


class SuggestICD10IntegrationRequest(BaseModel):
    """Request body for POST /ai-integration/suggest-icd10 (legacy integration)."""

    diagnosis: str = Field(..., min_length=1, max_length=5000, description="Diagnosis text for ICD-10 matching")
    specialty: str = Field("general", max_length=100, description="Medical specialty hint")
    language: Literal["ru", "uz", "en"] = Field("ru", description="Response language")
    provider: str | None = Field(None, max_length=50, description="AI provider hint")

    @field_validator("diagnosis")
    @classmethod
    def _strip_diagnosis(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("diagnosis must not be empty")
        return v


class AnalyzeDocumentIntegrationRequest(BaseModel):
    """Request body for POST /ai-integration/analyze-document (legacy integration)."""

    document_text: str = Field(..., min_length=1, max_length=50_000, description="Medical document text")
    document_type: Literal[
        "medical_report",
        "ultrasound_report",
        "ct_report",
        "mri_report",
        "xray_report",
        "lab_results",
        "discharge_summary",
        "consultation_note",
        "other",
    ] = Field("medical_report", description="Document type for AI context")
    specialty: str = Field("general", max_length=100, description="Medical specialty hint")

    @field_validator("document_text")
    @classmethod
    def _strip_document_text(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("document_text must not be empty")
        return v


class InterpretLabResultsIntegrationRequest(BaseModel):
    """Request body for POST /ai-integration/interpret-lab-results (legacy integration)."""

    lab_results: list[LabResultItem] | str = Field(
        ...,
        description="List of lab result items OR free-text lab results",
    )
    patient_age: int | None = Field(None, ge=0, le=150, description="Patient age in years")
    patient_gender: Literal["male", "female", "unknown"] = Field("unknown", description="Patient gender")
    specialty: str = Field("general", max_length=100, description="Medical specialty hint")

    @field_validator("lab_results")
    @classmethod
    def _validate_lab_results(cls, v):
        if isinstance(v, list):
            if not v:
                raise ValueError("lab_results list must not be empty")
            if len(v) > 200:
                raise ValueError("lab_results list must not exceed 200 items")
        elif isinstance(v, str):
            if not v.strip():
                raise ValueError("lab_results text must not be empty")
            if len(v) > 50_000:
                raise ValueError("lab_results text too long (max 50000 chars)")
        else:
            raise ValueError("lab_results must be a list or string")
        return v


class SymptomCheckerRequest(BaseModel):
    """Request body for POST /ai-integration/symptom-checker (triage help)."""

    symptoms: list[str] = Field(..., min_length=1, max_length=50, description="List of symptom strings")

    @field_validator("symptoms")
    @classmethod
    def _validate_symptoms(cls, v: list[str]) -> list[str]:
        cleaned = [s.strip() for s in v if isinstance(s, str) and s.strip()]
        if not cleaned:
            raise ValueError("symptoms must contain at least one non-empty string")
        return cleaned


class QuickDiagnosisHelpRequest(BaseModel):
    """Request body for POST /ai-integration/quick/diagnosis-help."""

    symptoms: str = Field("", max_length=10000, description="Symptoms text")
    current_diagnosis: str = Field("", max_length=5000, description="Preliminary diagnosis text")


__all__ = [
    # AI Gateway requests
    "AnalyzeComplaintsRequest",
    "SuggestICD10Request",
    "DifferentialDiagnosisRequest",
    "InterpretLabRequest",
    "AnalyzeSkinRequest",
    "AnalyzeECGRequest",
    "SymptomCheckRequest",
    "AnalyzeDocumentRequest",
    "DrugInteractionRequest",
    # AI Integration requests
    "AnalyzeComplaintsIntegrationRequest",
    "SuggestICD10IntegrationRequest",
    "AnalyzeDocumentIntegrationRequest",
    "InterpretLabResultsIntegrationRequest",
    "SymptomCheckerRequest",
    "QuickDiagnosisHelpRequest",
    # Shared
    "LabResultItem",
]

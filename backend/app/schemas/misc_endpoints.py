"""Pydantic schemas for remaining P0-9 endpoints.

P0-9 FIX (ENDPOINT-VALIDATION-AUDIT):
These schemas cover the remaining 17 endpoints that previously accepted
`dict[str, Any]` body parameters with no validation. For endpoints where
the expected fields are known (display_websocket, admin_display test,
registrar_integration reorder), typed models are used. For endpoints
where the dict is intentionally polymorphic (emr_ai, print_templates
preview, user_management preferences), a generic ValidatedDictBase model
enforces size caps and rejects dangerous deserialization keys.
"""
from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, model_validator

# Reuse the validation function from emr_export
from app.schemas.emr_export import _validate_dict_recursive


class ValidatedDictBase(BaseModel):
    """Base model for endpoints that accept a polymorphic dict body.

    Enforces:
    - Input must be a dict (not None, not a list, not a string)
    - No dangerous deserialization keys (__class__, __reduce__, etc.)
    - String value length caps (100KB per string)
    - Nesting depth limits (max 10 levels)
    - Top-level key count limits (max 100 keys)
    - List size limits (max 1000 items)
    """

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if data is None:
            return {}
        if not isinstance(data, dict):
            raise ValueError("request body must be a JSON object")
        _validate_dict_recursive(data)
        return data


# =============================================================================
# admin_display.py
# =============================================================================


class DisplayBannerRequest(ValidatedDictBase):
    """Request body for POST /display/boards/{board_id}/banners."""


class DisplayTestRequest(BaseModel):
    """Request body for POST /display/boards/{board_id}/test."""

    test_type: str = Field("call", max_length=50, description="Test type: call, announcement, etc.")
    board_ids: list[int] | None = Field(None, max_length=50, description="Specific board IDs to test")

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("test data must be a JSON object")
        _validate_dict_recursive(data)
        return data


# =============================================================================
# display_websocket.py
# =============================================================================


class CallPatientRequest(BaseModel):
    """Request body for POST /display/call-patient."""

    entry_id: int = Field(..., ge=1, description="Queue entry ID to call")
    board_ids: list[int] = Field(default_factory=list, max_length=50, description="Specific board IDs (empty = all)")

    model_config = {"extra": "forbid"}


class AnnouncementRequest(BaseModel):
    """Request body for POST /display/announcement."""

    text: str = Field(..., min_length=1, max_length=2000, description="Announcement text")
    type: str = Field("info", max_length=20, description="Announcement type: info, warning, emergency")
    duration: int = Field(60, ge=1, le=3600, description="Display duration in seconds (1-3600)")
    board_ids: list[int] = Field(default_factory=list, max_length=50, description="Specific board IDs (empty = all)")

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("announcement data must be a JSON object")
        return data


# =============================================================================
# doctor_integration.py
# =============================================================================


class CompleteVisitRequest(ValidatedDictBase):
    """Request body for POST /doctor/queue/{entry_id}/complete.

    visit_data is optional and polymorphic (may contain diagnosis,
    prescriptions, notes, etc.). When None, defaults to empty dict.
    """


# =============================================================================
# emr_ai.py + emr_ai_enhanced.py
# =============================================================================


class EmrAiTemplateDataRequest(ValidatedDictBase):
    """Polymorphic dict for EMR AI template_structure parameter."""


class EmrAiPatientDataRequest(ValidatedDictBase):
    """Polymorphic dict for EMR AI patient_data parameter."""


class EmrAiEmrDataRequest(ValidatedDictBase):
    """Polymorphic dict for EMR AI emr_data parameter."""


class EmrAiCurrentDataRequest(ValidatedDictBase):
    """Polymorphic dict for EMR AI current_data parameter."""


class EmrAiDoctorPreferencesRequest(ValidatedDictBase):
    """Polymorphic dict for EMR AI doctor_preferences parameter."""


# =============================================================================
# emr_versioning_enhanced.py
# =============================================================================


class EmrVersionDataRequest(ValidatedDictBase):
    """Request body for POST /emr/{emr_id}/versions/create."""


# =============================================================================
# print_templates.py
# =============================================================================


class PrintTemplatePreviewRequest(ValidatedDictBase):
    """Request body for POST /print/templates/{template_id}/preview.

    preview_data is polymorphic (different templates have different
    placeholder fields). Validated for size and dangerous keys.
    """


# =============================================================================
# registrar_integration.py
# =============================================================================


class ReorderQueueProfilesRequest(BaseModel):
    """Request body for POST /registrar/queues/profiles/reorder.

    Maps profile_key (str) → display_order (int).
    Example: {"cardiology": 1, "ecg": 2, "dermatology": 3}
    """

    model_config = {"extra": "allow"}

    @model_validator(mode="before")
    @classmethod
    def _validate_orders(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            raise ValueError("orders must be a JSON object")
        if len(data) > 50:
            raise ValueError("too many profile keys (max 50)")
        for key, value in data.items():
            if not isinstance(key, str):
                raise ValueError("profile keys must be strings")
            if not isinstance(value, int) or value < 0:
                raise ValueError(
                    f"profile order for '{key}' must be a non-negative integer"
                )
        return data


# =============================================================================
# user_management.py
# =============================================================================


class UserPreferencesRequest(ValidatedDictBase):
    """Request body for PUT /users/me/preferences.

    preferences_data is polymorphic (different users have different
    preference schemas). Validated for size and dangerous keys.
    """


__all__ = [
    "ValidatedDictBase",
    "DisplayBannerRequest",
    "DisplayTestRequest",
    "CallPatientRequest",
    "AnnouncementRequest",
    "CompleteVisitRequest",
    "EmrAiTemplateDataRequest",
    "EmrAiPatientDataRequest",
    "EmrAiEmrDataRequest",
    "EmrAiCurrentDataRequest",
    "EmrAiDoctorPreferencesRequest",
    "EmrVersionDataRequest",
    "PrintTemplatePreviewRequest",
    "ReorderQueueProfilesRequest",
    "UserPreferencesRequest",
]

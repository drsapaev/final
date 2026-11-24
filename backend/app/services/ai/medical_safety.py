"""Server-owned medical AI safety metadata shared by response boundaries.

This states a decision boundary, not that a suggestion is clinically correct.
Clients must verify it before displaying or applying any medical suggestion.
"""

from collections.abc import Mapping
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, field_validator


class MedicalAISafetyMeta(BaseModel):
    """A medical suggestion always requires an explicit doctor's review."""

    model_config = ConfigDict(frozen=True, revalidate_instances="always")

    requires_doctor_confirmation: Literal[True]

    @field_validator("requires_doctor_confirmation", mode="before")
    @classmethod
    def require_literal_true(cls, value: Any) -> bool:
        # Literal[True] alone accepts integer 1 before validation.
        if value is not True:
            raise ValueError("Doctor confirmation is required")
        return True


def medical_ai_safety_meta() -> dict[str, bool]:
    """Construct a fresh marker at an authoritative server boundary."""
    return {"requires_doctor_confirmation": True}


def with_medical_ai_safety(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Copy a server response and replace, never trust, provider metadata."""
    return {**payload, "ai_safety_meta": medical_ai_safety_meta()}

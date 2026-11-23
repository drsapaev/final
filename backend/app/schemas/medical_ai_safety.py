"""Response envelopes for medical suggestions requiring clinician review."""

from typing import Any

from pydantic import BaseModel, ConfigDict

from app.services.ai.medical_safety import MedicalAISafetyMeta


class MedicalAIResultResponse(BaseModel):
    """Preserve existing response fields while requiring server-owned safety metadata."""

    model_config = ConfigDict(extra="allow")

    ai_safety_meta: MedicalAISafetyMeta


class MedicalAIListResponse(BaseModel):
    """Envelope collections, including empty lists, with explicit safety metadata."""

    data: list[dict[str, Any]]
    ai_safety_meta: MedicalAISafetyMeta

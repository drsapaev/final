"""P1-17: Mock service replaced with stub.

This service returned hardcoded medical advice ("Парацетамол 500мг" for
ANY diagnosis) — clinically dangerous. Now returns error.
"""
import logging

logger = logging.getLogger(__name__)


class EMRService:
    """Stub — all methods return error indicating AI is not configured."""

    async def get_diagnosis_suggestions(self, symptoms, specialty="general"):
        return [{"error": "EMR AI service not implemented. Configure a real AI provider."}]

    async def get_treatment_suggestions(self, diagnosis, specialty="general"):
        return [{"error": "EMR AI service not implemented. Configure a real AI provider."}]

    async def get_icd10_suggestions(self, diagnosis):
        return [{"error": "EMR AI service not implemented."}]


_emr_service = EMRService()

def get_emr_ai_service():
    return _emr_service

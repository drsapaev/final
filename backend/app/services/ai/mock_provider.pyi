"""
Type stubs for MockProvider - mock провайдер для тестирования и демонстрации.

Этот файл предоставляет type hints для mypy без изменения runtime кода.
"""

from typing import Any

from .base_provider import AIRequest, AIResponse, BaseAIProvider

class MockProvider(BaseAIProvider):
    """Mock провайдер для демонстрации функционала без реального API."""

    def __init__(self, api_key: str = "mock", model: str | None = None) -> None: ...

    def get_default_model(self) -> str: ...

    async def generate(self, request: AIRequest) -> AIResponse: ...

    async def analyze_complaint(
        self, complaint: str, patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def suggest_icd10(
        self, symptoms: list[str], diagnosis: str | None = None
    ) -> AIResponse: ...

    async def interpret_lab_results(
        self, results: list[dict[str, Any]], patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    def _get_clinical_significance(self, parameter: str, is_high: bool) -> str: ...

    async def analyze_skin(
        self, image_data: bytes, metadata: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def interpret_ecg(
        self, ecg_data: dict[str, Any], patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def differential_diagnosis(
        self, symptoms: list[str], patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def symptom_analysis(
        self, symptoms: list[str], severity: list[int] | None = None
    ) -> AIResponse: ...

    async def clinical_decision_support(
        self, case_data: dict[str, Any]
    ) -> AIResponse: ...

    async def analyze_xray_image(
        self, image_data: bytes, metadata: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def analyze_ultrasound_image(
        self, image_data: bytes, metadata: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def analyze_dermatoscopy_image(
        self, image_data: bytes, metadata: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def analyze_medical_image_generic(
        self, image_data: bytes, image_type: str, metadata: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def generate_treatment_plan(
        self,
        patient_data: dict[str, Any],
        diagnosis: str,
        medical_history: list[dict[str, Any]] | None = None,
    ) -> AIResponse: ...

    async def optimize_medication_regimen(
        self,
        current_medications: list[dict[str, Any]],
        patient_profile: dict[str, Any],
        condition: str,
    ) -> AIResponse: ...

    async def assess_treatment_effectiveness(
        self, treatment_history: list[dict[str, Any]], patient_response: dict[str, Any]
    ) -> AIResponse: ...

    async def suggest_lifestyle_modifications(
        self, patient_profile: dict[str, Any], conditions: list[str]
    ) -> AIResponse: ...

    async def check_drug_interactions(
        self,
        medications: list[dict[str, Any]],
        patient_profile: dict[str, Any] | None = None,
    ) -> AIResponse: ...

    async def analyze_drug_safety(
        self,
        medication: dict[str, Any],
        patient_profile: dict[str, Any],
        conditions: list[str],
    ) -> AIResponse: ...

    async def suggest_drug_alternatives(
        self, medication: dict[str, Any], reason: str
    ) -> AIResponse: ...

    async def analyze_medical_trends(
        self, medical_data: list[dict[str, Any]], time_period: str, analysis_type: str
    ) -> AIResponse: ...

    async def calculate_mortality_risk(
        self, patient_data: dict[str, Any], conditions: list[str]
    ) -> AIResponse: ...

    async def generate_prognosis(
        self,
        patient_data: dict[str, Any],
        procedure_or_condition: str,
        timeline: str,
    ) -> AIResponse: ...

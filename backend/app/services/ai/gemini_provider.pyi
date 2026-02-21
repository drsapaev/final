"""
Type stubs for GeminiProvider - провайдер Google Gemini для AI функций.

Этот файл предоставляет type hints для mypy без изменения runtime кода.
"""

from typing import Any

from .base_provider import AIRequest, AIResponse, BaseAIProvider

class GeminiProvider(BaseAIProvider):
    """Провайдер Google Gemini с полной реализацией."""

    def __init__(self, api_key: str, model: str | None = None) -> None: ...

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

    async def analyze_skin(
        self, image_data: bytes, metadata: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def analyze_medical_image_generic(
        self, image_data: bytes, image_type: str, metadata: dict[str, Any] | None = None
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

    async def interpret_ecg(
        self, ecg_data: str, metadata: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def generate_treatment_plan(
        self, diagnosis: str, patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def clinical_decision_support(
        self, symptoms: list[str], patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def differential_diagnosis(
        self, symptoms: list[str], patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def drug_interaction_check(self, medications: list[str]) -> AIResponse: ...

    async def medical_literature_search(self, query: str) -> AIResponse: ...

    async def analyze_documentation_quality(self, text: str) -> AIResponse: ...

    async def analyze_drug_safety(
        self, drug: str, patient_info: dict[str, Any] | None = None
    ) -> AIResponse: ...

    async def analyze_medical_trends(
        self, medical_data: list[dict[str, Any]], time_period: str, analysis_type: str
    ) -> AIResponse: ...

    async def analyze_workload_distribution(self, data: dict[str, Any]) -> AIResponse: ...

    async def assess_emergency_level(self, symptoms: list[str]) -> AIResponse: ...

    async def assess_patient_risk(self, patient_info: dict[str, Any]) -> AIResponse: ...

    async def assess_surgical_risk(
        self, patient_info: dict[str, Any], procedure: str
    ) -> AIResponse: ...

    async def assess_treatment_effectiveness(
        self, treatment: str, outcomes: list[dict[str, Any]]
    ) -> AIResponse: ...

    async def generate_shift_recommendations(self, data: dict[str, Any]) -> AIResponse: ...

    async def identify_risk_patterns(self, data: list[dict[str, Any]]) -> AIResponse: ...

    async def optimize_doctor_schedule(self, data: dict[str, Any]) -> AIResponse: ...

    async def optimize_medication_regimen(
        self, medications: list[str], patient_info: dict[str, Any]
    ) -> AIResponse: ...

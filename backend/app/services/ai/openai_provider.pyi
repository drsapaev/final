"""
Type stubs for OpenAIProvider - провайдер OpenAI для AI функций.

Этот файл предоставляет type hints для mypy без изменения runtime кода.
"""

from typing import Any, Dict, List, Optional

from .base_provider import AIRequest, AIResponse, BaseAIProvider


class OpenAIProvider(BaseAIProvider):
    """Провайдер OpenAI (GPT-4, GPT-3.5)."""

    def __init__(self, api_key: str, model: Optional[str] = None) -> None: ...
    
    def get_default_model(self) -> str: ...
    
    async def generate(self, request: AIRequest) -> AIResponse: ...
    
    async def analyze_complaint(
        self, complaint: str, patient_info: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def differential_diagnosis(
        self, symptoms: List[str], patient_info: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def symptom_analysis(
        self, symptoms: List[str], severity: Optional[List[int]] = None
    ) -> AIResponse: ...
    
    async def clinical_decision_support(
        self, case_data: Dict[str, Any]
    ) -> AIResponse: ...
    
    async def suggest_icd10(
        self, symptoms: List[str], diagnosis: Optional[str] = None
    ) -> AIResponse: ...
    
    async def interpret_lab_results(
        self, results: List[Dict[str, Any]], patient_info: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def analyze_skin(
        self, image_data: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def interpret_ecg(
        self, ecg_data: Dict[str, Any], patient_info: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def analyze_xray_image(
        self, image_data: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def analyze_ultrasound_image(
        self, image_data: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def analyze_dermatoscopy_image(
        self, image_data: bytes, metadata: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def analyze_medical_image_generic(
        self, image_data: bytes, image_type: str, metadata: Optional[Dict[str, Any]] = None
    ) -> AIResponse: ...
    
    async def generate_treatment_plan(
        self,
        patient_data: Dict[str, Any],
        diagnosis: str,
        medical_history: Optional[List[Dict[str, Any]]] = None,
    ) -> AIResponse: ...
    
    async def drug_interaction_check(
        self, medications: List[str]
    ) -> AIResponse: ...
    
    async def check_drug_interactions(
        self, medication: Dict[str, Any], patient_profile: Dict[str, Any], conditions: List[str]
    ) -> AIResponse: ...
    
    async def suggest_drug_alternatives(
        self, medication: Dict[str, Any], reason: str
    ) -> AIResponse: ...
    
    async def analyze_medical_trends(
        self, medical_data: List[Dict[str, Any]], time_period: str, analysis_type: str
    ) -> AIResponse: ...

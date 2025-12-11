"""
Type stubs for AIManager - полная типизация AI сервисов.

Этот файл предоставляет type hints для mypy без изменения runtime кода.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from .base_provider import AIResponse, BaseAIProvider


class AIProviderType(Enum):
    """Типы AI провайдеров."""
    OPENAI: str
    GEMINI: str
    DEEPSEEK: str
    MOCK: str


class AIManager:
    """
    Менеджер для работы с AI провайдерами.
    
    Attributes:
        providers: Словарь доступных провайдеров
        default_provider: Провайдер по умолчанию
    """
    
    providers: Dict[AIProviderType, BaseAIProvider]
    default_provider: Optional[AIProviderType]
    
    def __init__(self) -> None: ...
    
    def _initialize_providers(self) -> None: ...
    
    def get_provider(
        self, 
        provider_type: Optional[AIProviderType] = None
    ) -> BaseAIProvider: ...
    
    def set_default_provider(self, provider_type: AIProviderType) -> None: ...
    
    def get_available_providers(self) -> List[AIProviderType]: ...
    
    async def generate(
        self, 
        prompt: str, 
        provider_type: Optional[AIProviderType] = None, 
        **kwargs: Any
    ) -> AIResponse: ...
    
    async def analyze_complaint(
        self,
        complaint: str,
        patient_info: Optional[Dict[str, Any]] = None,
        provider_type: Optional[AIProviderType] = None,
    ) -> AIResponse: ...
    
    async def suggest_icd10(
        self,
        symptoms: List[str],
        diagnosis: Optional[str] = None,
        provider_type: Optional[AIProviderType] = None,
    ) -> AIResponse: ...
    
    async def interpret_lab_results(
        self,
        results: List[Dict[str, Any]],
        patient_info: Optional[Dict[str, Any]] = None,
        provider_type: Optional[AIProviderType] = None,
    ) -> AIResponse: ...
    
    async def analyze_skin(
        self,
        image_data: bytes,
        metadata: Optional[Dict[str, Any]] = None,
        provider_type: Optional[AIProviderType] = None,
    ) -> AIResponse: ...
    
    async def interpret_ecg(
        self,
        ecg_data: Dict[str, Any],
        patient_info: Optional[Dict[str, Any]] = None,
        provider_type: Optional[AIProviderType] = None,
    ) -> AIResponse: ...
    
    async def analyze_medical_trends(
        self,
        medical_data: List[Dict[str, Any]],
        time_period: str,
        analysis_type: str,
        provider: Optional[AIProviderType] = None,
    ) -> AIResponse: ...


# Глобальный экземпляр менеджера
ai_manager: AIManager


def get_ai_manager() -> AIManager:
    """Получить глобальный экземпляр AI менеджера."""
    ...

"""
Type stubs for AIManager - полная типизация AI сервисов.

Этот файл предоставляет type hints для mypy без изменения runtime кода.
"""

from enum import Enum
from typing import Any

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

    providers: dict[AIProviderType, BaseAIProvider]
    default_provider: AIProviderType | None

    def __init__(self) -> None: ...

    def _initialize_providers(self) -> None: ...

    def get_provider(
        self,
        provider_type: AIProviderType | None = None
    ) -> BaseAIProvider: ...

    def set_default_provider(self, provider_type: AIProviderType) -> None: ...

    def get_available_providers(self) -> list[AIProviderType]: ...

    async def generate(
        self,
        prompt: str,
        provider_type: AIProviderType | None = None,
        **kwargs: Any
    ) -> AIResponse: ...

    async def analyze_complaint(
        self,
        complaint: str,
        patient_info: dict[str, Any] | None = None,
        provider_type: AIProviderType | None = None,
    ) -> AIResponse: ...

    async def suggest_icd10(
        self,
        symptoms: list[str],
        diagnosis: str | None = None,
        provider_type: AIProviderType | None = None,
    ) -> AIResponse: ...

    async def interpret_lab_results(
        self,
        results: list[dict[str, Any]],
        patient_info: dict[str, Any] | None = None,
        provider_type: AIProviderType | None = None,
    ) -> AIResponse: ...

    async def analyze_skin(
        self,
        image_data: bytes,
        metadata: dict[str, Any] | None = None,
        provider_type: AIProviderType | None = None,
    ) -> AIResponse: ...

    async def interpret_ecg(
        self,
        ecg_data: dict[str, Any],
        patient_info: dict[str, Any] | None = None,
        provider_type: AIProviderType | None = None,
    ) -> AIResponse: ...

    async def analyze_medical_trends(
        self,
        medical_data: list[dict[str, Any]],
        time_period: str,
        analysis_type: str,
        provider: AIProviderType | None = None,
    ) -> AIResponse: ...


# Глобальный экземпляр менеджера
ai_manager: AIManager


def get_ai_manager() -> AIManager:
    """Получить глобальный экземпляр AI менеджера."""
    ...

"""
Type stubs for BaseAIProvider - базовый класс для AI провайдеров.

Этот файл предоставляет type hints для mypy без изменения runtime кода.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any

class AITaskType(Enum):
    """Типы AI задач."""
    COMPLAINT_ANALYSIS: str
    ICD10_SUGGESTION: str
    LAB_INTERPRETATION: str
    SKIN_ANALYSIS: str
    ECG_INTERPRETATION: str
    MEDICAL_TRENDS: str
    GENERAL: str


@dataclass
class AIRequest:
    """Запрос к AI провайдеру."""

    prompt: str
    task_type: AITaskType
    specialty: str | None
    context: dict[str, Any] | None
    temperature: float | None
    max_tokens: int | None

    def __init__(
        self,
        prompt: str,
        task_type: AITaskType = AITaskType.GENERAL,
        specialty: str | None = None,
        context: dict[str, Any] | None = None,
        temperature: float | None = None,
        max_tokens: int | None = None,
    ) -> None: ...


@dataclass
class AIResponse:
    """Ответ от AI провайдера."""

    content: str
    raw_response: dict[str, Any] | None
    tokens_used: int | None
    response_time_ms: int | None
    cached: bool
    provider: str
    model: str
    error: str | None
    success: bool
    timestamp: datetime

    def __init__(
        self,
        content: str = "",
        raw_response: dict[str, Any] | None = None,
        tokens_used: int | None = None,
        response_time_ms: int | None = None,
        cached: bool = False,
        provider: str = "",
        model: str = "",
        error: str | None = None,
        success: bool = True,
        timestamp: datetime | None = None,
    ) -> None: ...

    def to_dict(self) -> dict[str, Any]: ...

    @classmethod
    def error_response(cls, error: str, provider: str = "") -> AIResponse: ...


class BaseAIProvider(ABC):
    """
    Базовый класс для AI провайдеров.

    Все конкретные провайдеры (OpenAI, Gemini, DeepSeek)
    наследуют этот класс и реализуют абстрактные методы.
    """

    name: str
    display_name: str
    api_key: str | None
    model: str
    temperature: float
    max_tokens: int

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int = 1000,
    ) -> None: ...

    @abstractmethod
    async def generate(self, request: AIRequest) -> AIResponse:
        """Основной метод генерации текста."""
        ...

    @abstractmethod
    async def is_available(self) -> bool:
        """Проверить доступность провайдера."""
        ...

    async def analyze_complaint(
        self,
        complaint: str,
        patient_info: dict[str, Any] | None = None,
    ) -> AIResponse: ...

    async def suggest_icd10(
        self,
        symptoms: list[str],
        diagnosis: str | None = None,
    ) -> AIResponse: ...

    async def interpret_lab_results(
        self,
        results: list[dict[str, Any]],
        patient_info: dict[str, Any] | None = None,
    ) -> AIResponse: ...

    async def analyze_image(
        self,
        image_data: bytes,
        analysis_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> AIResponse: ...

    def _build_prompt(
        self,
        task_type: AITaskType,
        **kwargs: Any,
    ) -> str: ...

    def _parse_response(
        self,
        raw_response: dict[str, Any],
    ) -> str: ...

"""
Type stubs for BaseAIProvider - базовый класс для AI провайдеров.

Этот файл предоставляет type hints для mypy без изменения runtime кода.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Union


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
    specialty: Optional[str]
    context: Optional[Dict[str, Any]]
    temperature: Optional[float]
    max_tokens: Optional[int]
    
    def __init__(
        self,
        prompt: str,
        task_type: AITaskType = AITaskType.GENERAL,
        specialty: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> None: ...


@dataclass
class AIResponse:
    """Ответ от AI провайдера."""
    
    content: str
    raw_response: Optional[Dict[str, Any]]
    tokens_used: Optional[int]
    response_time_ms: Optional[int]
    cached: bool
    provider: str
    model: str
    error: Optional[str]
    success: bool
    timestamp: datetime
    
    def __init__(
        self,
        content: str = "",
        raw_response: Optional[Dict[str, Any]] = None,
        tokens_used: Optional[int] = None,
        response_time_ms: Optional[int] = None,
        cached: bool = False,
        provider: str = "",
        model: str = "",
        error: Optional[str] = None,
        success: bool = True,
        timestamp: Optional[datetime] = None,
    ) -> None: ...
    
    def to_dict(self) -> Dict[str, Any]: ...
    
    @classmethod
    def error_response(cls, error: str, provider: str = "") -> "AIResponse": ...


class BaseAIProvider(ABC):
    """
    Базовый класс для AI провайдеров.
    
    Все конкретные провайдеры (OpenAI, Gemini, DeepSeek) 
    наследуют этот класс и реализуют абстрактные методы.
    """
    
    name: str
    display_name: str
    api_key: Optional[str]
    model: str
    temperature: float
    max_tokens: int
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
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
        patient_info: Optional[Dict[str, Any]] = None,
    ) -> AIResponse: ...
    
    async def suggest_icd10(
        self,
        symptoms: List[str],
        diagnosis: Optional[str] = None,
    ) -> AIResponse: ...
    
    async def interpret_lab_results(
        self,
        results: List[Dict[str, Any]],
        patient_info: Optional[Dict[str, Any]] = None,
    ) -> AIResponse: ...
    
    async def analyze_image(
        self,
        image_data: bytes,
        analysis_type: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AIResponse: ...
    
    def _build_prompt(
        self,
        task_type: AITaskType,
        **kwargs: Any,
    ) -> str: ...
    
    def _parse_response(
        self,
        raw_response: Dict[str, Any],
    ) -> str: ...

"""
AI Interfaces - Единые контракты для всех AI операций
SSOT для типов задач и форматов ответов
"""

from abc import ABC, abstractmethod
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class AITaskType(str, Enum):
    """SSOT для типов AI задач"""
    COMPLAINT_ANALYSIS = "complaint_analysis"
    ICD10_SUGGESTION = "icd10_suggestion"
    LAB_INTERPRETATION = "lab_interpretation"
    IMAGE_ANALYSIS = "image_analysis"
    SKIN_ANALYSIS = "skin_analysis"
    ECG_INTERPRETATION = "ecg_interpretation"
    TREATMENT_PLAN = "treatment_plan"
    DIFFERENTIAL_DIAGNOSIS = "differential_diagnosis"
    CHAT_MESSAGE = "chat_message"
    DOCUMENT_ANALYSIS = "document_analysis"
    DRUG_INTERACTION = "drug_interaction"
    SYMPTOM_CHECK = "symptom_check"


class AIProviderType(str, Enum):
    """Типы AI провайдеров"""
    OPENAI = "openai"
    GEMINI = "gemini"
    DEEPSEEK = "deepseek"
    MOCK = "mock"


class AIResponse(BaseModel):
    """
    Единый контракт ответа для ВСЕХ AI endpoints.

    Frontend всегда получает этот формат, независимо от провайдера или task type.
    """
    status: str = Field(..., description="success | error | partial")
    data: dict[str, Any] = Field(default_factory=dict, description="Результат AI операции")
    provider: str = Field(..., description="openai | gemini | deepseek | mock")
    model: str = Field(..., description="gpt-4, gemini-1.5-flash, deepseek-chat")
    latency_ms: int = Field(..., ge=0, description="Время выполнения в миллисекундах")
    tokens_used: int | None = Field(None, ge=0, description="Количество использованных токенов")
    cached: bool = Field(False, description="Ответ из кэша")
    error: str | None = Field(None, description="Сообщение об ошибке")
    warnings: list[str] = Field(default_factory=list, description="Предупреждения")

    # Medical compliance
    disclaimer: str = Field(
        default="AI suggestions are advisory only. Final decisions must be made by licensed medical professionals.",
        description="Медицинский дисклеймер"
    )
    confidence: float | None = Field(None, ge=0.0, le=1.0, description="Уверенность AI (0.0-1.0)")

    # Metadata
    request_id: str | None = Field(None, description="Уникальный ID запроса для трекинга")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Время ответа")


class AIICD10Suggestion(BaseModel):
    """Структура для ICD-10 подсказки"""
    code: str = Field(..., description="Код МКБ-10 (например, I10)")
    description: str = Field(..., description="Описание диагноза")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Уверенность")
    category: str | None = Field(None, description="Категория (primary, secondary)")


class AIICD10Response(AIResponse):
    """Специализированный ответ для ICD-10 подсказок"""
    suggestions: list[AIICD10Suggestion] = Field(default_factory=list)


class AIComplaintAnalysis(BaseModel):
    """Структура анализа жалоб"""
    summary: str = Field(..., description="Краткое описание")
    possible_conditions: list[str] = Field(default_factory=list)
    recommended_tests: list[str] = Field(default_factory=list)
    urgency_level: str = Field("routine", description="emergency | urgent | routine")
    red_flags: list[str] = Field(default_factory=list, description="Тревожные симптомы")


class AIComplaintResponse(AIResponse):
    """Специализированный ответ для анализа жалоб"""
    analysis: AIComplaintAnalysis | None = None


class AILabInterpretation(BaseModel):
    """Структура интерпретации анализов"""
    summary: str = Field(..., description="Общее заключение")
    abnormal_values: list[dict[str, Any]] = Field(default_factory=list)
    clinical_significance: str = Field("", description="Клиническое значение")
    recommendations: list[str] = Field(default_factory=list)


class AILabResponse(AIResponse):
    """Специализированный ответ для интерпретации анализов"""
    interpretation: AILabInterpretation | None = None


class AIImageAnalysis(BaseModel):
    """Структура анализа изображения"""
    description: str = Field(..., description="Описание находок")
    findings: list[str] = Field(default_factory=list)
    abnormalities: list[dict[str, Any]] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    requires_specialist: bool = Field(False)


class AIImageResponse(AIResponse):
    """Специализированный ответ для анализа изображений"""
    analysis: AIImageAnalysis | None = None


class IAnonymizer(ABC):
    """Интерфейс для анонимизации PII"""

    @abstractmethod
    def anonymize(self, data: dict[str, Any]) -> dict[str, Any]:
        """Удаляет/маскирует персональные данные"""
        pass

    @abstractmethod
    def get_anonymized_fields(self) -> list[str]:
        """Возвращает список полей, которые были анонимизированы"""
        pass


class IAIGateway(ABC):
    """
    Интерфейс для единого AI Gateway.

    Все AI операции проходят через этот интерфейс,
    обеспечивая единообразие, аудит и безопасность.
    """

    @abstractmethod
    async def execute(
        self,
        task_type: AITaskType,
        payload: dict[str, Any],
        user_id: int,
        specialty: str | None = None
    ) -> AIResponse:
        """
        Единая точка входа для всех AI операций.

        Args:
            task_type: Тип AI задачи
            payload: Данные для обработки
            user_id: ID пользователя (для аудита и rate limiting)
            specialty: Специализация врача (опционально)

        Returns:
            Унифицированный AIResponse
        """
        pass

    @abstractmethod
    async def execute_stream(
        self,
        task_type: AITaskType,
        payload: dict[str, Any],
        user_id: int,
        specialty: str | None = None
    ):
        """
        Streaming версия для чата.

        Yields:
            Chunks текста для realtime UI
        """
        pass

    @abstractmethod
    def get_available_providers(self) -> list[AIProviderType]:
        """Список доступных (сконфигурированных) провайдеров"""
        pass

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Проверка здоровья всех провайдеров"""
        pass

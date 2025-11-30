"""
Схемы для трекинга AI моделей в авто режиме
"""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class AIModelInfo(BaseModel):
    """Информация о AI модели, выполнившей запрос"""

    model_config = ConfigDict(protected_namespaces=())

    provider_id: int = Field(..., description="ID провайдера")
    provider_name: str = Field(
        ..., description="Название провайдера (OpenAI, Gemini, etc.)"
    )
    model_name: str = Field(
        ..., description="Название модели (gpt-4, gemini-pro, etc.)"
    )
    model_version: Optional[str] = Field(None, description="Версия модели")
    temperature: float = Field(..., description="Температура генерации")
    max_tokens: int = Field(..., description="Максимальное количество токенов")
    capabilities: Optional[Dict[str, Any]] = Field(
        None, description="Возможности модели"
    )


class AIRequestTracking(BaseModel):
    """Трекинг AI запроса"""

    model_config = ConfigDict(protected_namespaces=())

    request_id: str = Field(..., description="Уникальный ID запроса")
    task_type: str = Field(
        ..., description="Тип задачи (analyze_complaints, generate_prescription, etc.)"
    )
    specialty: Optional[str] = Field(
        None, description="Специализация (cardio, derma, dental, etc.)"
    )
    user_id: Optional[int] = Field(None, description="ID пользователя")

    # Информация о модели
    model_info: AIModelInfo = Field(..., description="Информация о AI модели")

    # Метрики производительности
    response_time_ms: int = Field(..., description="Время ответа в миллисекундах")
    tokens_used: int = Field(..., description="Количество использованных токенов")
    success: bool = Field(..., description="Успешность выполнения")
    error_message: Optional[str] = Field(None, description="Сообщение об ошибке")

    # Кэширование
    cached_response: bool = Field(False, description="Был ли ответ из кэша")
    request_hash: Optional[str] = Field(None, description="Хеш запроса для кэширования")

    # Временные метки
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Время создания запроса"
    )
    completed_at: Optional[datetime] = Field(
        None, description="Время завершения запроса"
    )


class AIResponseWithTracking(BaseModel):
    """Ответ AI с информацией о модели"""

    model_config = ConfigDict(protected_namespaces=())

    data: Dict[str, Any] = Field(..., description="Основные данные ответа")
    tracking: AIRequestTracking = Field(..., description="Информация о трекинге")

    # Дополнительная информация
    model_confidence: Optional[float] = Field(
        None, description="Уверенность модели (0-1)"
    )
    processing_notes: Optional[str] = Field(None, description="Заметки о обработке")


class AIModelStats(BaseModel):
    """Статистика использования AI моделей"""

    provider_name: str
    model_name: str
    total_requests: int
    successful_requests: int
    failed_requests: int
    average_response_time_ms: float
    total_tokens_used: int
    cache_hit_rate: float
    last_used: Optional[datetime] = None


class AIProviderStats(BaseModel):
    """Статистика провайдера AI"""

    provider_id: int
    provider_name: str
    display_name: str
    is_active: bool
    is_default: bool
    models: list[AIModelStats] = Field(default_factory=list)
    total_requests: int = 0
    success_rate: float = 0.0
    average_response_time_ms: float = 0.0

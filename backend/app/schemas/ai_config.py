"""
Pydantic схемы для AI конфигурации
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ===================== AI ПРОВАЙДЕРЫ =====================


class AIProviderBase(BaseModel):
    name: str = Field(..., max_length=50, description="Уникальное имя провайдера")
    display_name: str = Field(..., max_length=100, description="Отображаемое имя")
    api_key: str | None = Field(None, max_length=200, description="API ключ")
    api_url: str | None = Field(None, max_length=200, description="Базовый URL API")
    model: str | None = Field(None, max_length=100, description="Модель AI")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Температура генерации")
    max_tokens: int = Field(1000, ge=1, le=8000, description="Максимум токенов")
    active: bool = Field(False, description="Активен ли провайдер")
    is_default: bool = Field(False, description="Провайдер по умолчанию")
    capabilities: list[str] | None = Field(
        None, description="Возможности: text, vision, ocr"
    )
    limits: dict[str, int] | None = Field(None, description="Лимиты использования")


class AIProviderCreate(AIProviderBase):
    pass


class AIProviderUpdate(BaseModel):
    display_name: str | None = Field(None, max_length=100)
    api_key: str | None = Field(None, max_length=200)
    api_url: str | None = Field(None, max_length=200)
    model: str | None = Field(None, max_length=100)
    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=8000)
    active: bool | None = None
    is_default: bool | None = None
    capabilities: list[str] | None = None
    limits: dict[str, int] | None = None


class AIProviderOut(AIProviderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Скрываем API ключ в ответе
    api_key: str | None = Field(
        None, description="Скрыт из соображений безопасности"
    )


class AIProviderTestRequest(BaseModel):
    """Запрос на тестирование AI провайдера"""

    test_prompt: str = Field("Привет, как дела?", description="Тестовый промпт")
    task_type: str = Field("text", description="Тип задачи: text, vision, ocr")


# ===================== ШАБЛОНЫ ПРОМПТОВ =====================


class AIPromptTemplateBase(BaseModel):
    provider_id: int
    task_type: str = Field(
        ..., max_length=50, description="complaints2plan, icd10, lab_interpret"
    )
    specialty: str | None = Field(
        None, max_length=50, description="cardiology, dermatology, stomatology"
    )
    language: str = Field("ru", max_length=5, description="Язык: ru, uz, en")
    version: str = Field("1.0", max_length=20, description="Версия шаблона")

    system_prompt: str = Field(..., description="Системный промпт")
    context_template: str | None = Field(None, description="Шаблон контекста")
    task_template: str = Field(..., description="Шаблон задачи")
    examples: list[dict[str, Any]] | None = Field(
        None, description="Примеры для few-shot"
    )

    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=8000)
    response_schema: dict[str, Any] | None = Field(
        None, description="JSON Schema ответа"
    )
    active: bool = True


class AIPromptTemplateCreate(AIPromptTemplateBase):
    pass


class AIPromptTemplateUpdate(BaseModel):
    task_type: str | None = Field(None, max_length=50)
    specialty: str | None = Field(None, max_length=50)
    language: str | None = Field(None, max_length=5)
    version: str | None = Field(None, max_length=20)

    system_prompt: str | None = None
    context_template: str | None = None
    task_template: str | None = None
    examples: list[dict[str, Any]] | None = None

    temperature: float | None = Field(None, ge=0.0, le=2.0)
    max_tokens: int | None = Field(None, ge=1, le=8000)
    response_schema: dict[str, Any] | None = None
    active: bool | None = None


class AIPromptTemplateOut(AIPromptTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    provider: dict[str, Any] | None = None


# ===================== ЛОГИ ИСПОЛЬЗОВАНИЯ =====================


class AIUsageLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    provider_id: int
    task_type: str
    specialty: str | None = None
    tokens_used: int | None = None
    response_time_ms: int | None = None
    success: bool
    error_message: str | None = None
    cached_response: bool
    created_at: datetime | None = None


# ===================== НАСТРОЙКИ AI СИСТЕМЫ =====================


class AISystemSettings(BaseModel):
    """Общие настройки AI системы"""

    enabled: bool = Field(True, description="Включена ли AI система")
    default_provider: str = Field("openai", description="Провайдер по умолчанию")
    fallback_chain: list[str] = Field(
        default=["openai", "gemini", "deepseek"],
        description="Цепочка fallback провайдеров",
    )
    cache_enabled: bool = Field(True, description="Включено ли кэширование")
    cache_ttl_hours: int = Field(24, ge=1, le=168, description="TTL кэша в часах")

    # Глобальные лимиты
    global_limits: dict[str, int] = Field(
        default={
            "requests_per_minute": 60,
            "tokens_per_day": 50000,
            "max_file_size_mb": 10,
        },
        description="Глобальные лимиты системы",
    )

    # Настройки безопасности
    require_consent_for_files: bool = Field(
        True, description="Требовать согласие для обработки файлов"
    )
    anonymize_data: bool = Field(
        True, description="Анонимизировать персональные данные"
    )
    audit_all_requests: bool = Field(True, description="Логировать все запросы")


class AITestResult(BaseModel):
    """Результат тестирования AI провайдера"""

    success: bool
    response_text: str | None = None
    response_time_ms: int | None = None
    tokens_used: int | None = None
    error_message: str | None = None
    provider_info: dict[str, Any] = {}


# ===================== СТАТИСТИКА AI =====================


class AIStatsResponse(BaseModel):
    """Статистика использования AI"""

    total_requests: int
    successful_requests: int
    failed_requests: int
    total_tokens_used: int
    average_response_time_ms: float
    cache_hit_rate: float

    # По провайдерам
    by_provider: dict[str, dict[str, Any]]

    # По типам задач
    by_task_type: dict[str, dict[str, Any]]

    # По специальностям
    by_specialty: dict[str, dict[str, Any]]

    # За период
    period_start: datetime
    period_end: datetime

"""
Pydantic схемы для AI конфигурации
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


# ===================== AI ПРОВАЙДЕРЫ =====================

class AIProviderBase(BaseModel):
    name: str = Field(..., max_length=50, description="Уникальное имя провайдера")
    display_name: str = Field(..., max_length=100, description="Отображаемое имя")
    api_key: Optional[str] = Field(None, max_length=200, description="API ключ")
    api_url: Optional[str] = Field(None, max_length=200, description="Базовый URL API")
    model: Optional[str] = Field(None, max_length=100, description="Модель AI")
    temperature: float = Field(0.2, ge=0.0, le=2.0, description="Температура генерации")
    max_tokens: int = Field(1000, ge=1, le=8000, description="Максимум токенов")
    active: bool = Field(False, description="Активен ли провайдер")
    is_default: bool = Field(False, description="Провайдер по умолчанию")
    capabilities: Optional[List[str]] = Field(None, description="Возможности: text, vision, ocr")
    limits: Optional[Dict[str, int]] = Field(None, description="Лимиты использования")


class AIProviderCreate(AIProviderBase):
    pass


class AIProviderUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=100)
    api_key: Optional[str] = Field(None, max_length=200)
    api_url: Optional[str] = Field(None, max_length=200)
    model: Optional[str] = Field(None, max_length=100)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=8000)
    active: Optional[bool] = None
    is_default: Optional[bool] = None
    capabilities: Optional[List[str]] = None
    limits: Optional[Dict[str, int]] = None


class AIProviderOut(AIProviderBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    # Скрываем API ключ в ответе
    api_key: Optional[str] = Field(None, description="Скрыт из соображений безопасности")


class AIProviderTestRequest(BaseModel):
    """Запрос на тестирование AI провайдера"""
    test_prompt: str = Field("Привет, как дела?", description="Тестовый промпт")
    task_type: str = Field("text", description="Тип задачи: text, vision, ocr")


# ===================== ШАБЛОНЫ ПРОМПТОВ =====================

class AIPromptTemplateBase(BaseModel):
    provider_id: int
    task_type: str = Field(..., max_length=50, description="complaints2plan, icd10, lab_interpret")
    specialty: Optional[str] = Field(None, max_length=50, description="cardiology, dermatology, stomatology")
    language: str = Field("ru", max_length=5, description="Язык: ru, uz, en")
    version: str = Field("1.0", max_length=20, description="Версия шаблона")
    
    system_prompt: str = Field(..., description="Системный промпт")
    context_template: Optional[str] = Field(None, description="Шаблон контекста")
    task_template: str = Field(..., description="Шаблон задачи")
    examples: Optional[List[Dict[str, Any]]] = Field(None, description="Примеры для few-shot")
    
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=8000)
    response_schema: Optional[Dict[str, Any]] = Field(None, description="JSON Schema ответа")
    active: bool = True


class AIPromptTemplateCreate(AIPromptTemplateBase):
    pass


class AIPromptTemplateUpdate(BaseModel):
    task_type: Optional[str] = Field(None, max_length=50)
    specialty: Optional[str] = Field(None, max_length=50)
    language: Optional[str] = Field(None, max_length=5)
    version: Optional[str] = Field(None, max_length=20)
    
    system_prompt: Optional[str] = None
    context_template: Optional[str] = None
    task_template: Optional[str] = None
    examples: Optional[List[Dict[str, Any]]] = None
    
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    max_tokens: Optional[int] = Field(None, ge=1, le=8000)
    response_schema: Optional[Dict[str, Any]] = None
    active: Optional[bool] = None


class AIPromptTemplateOut(AIPromptTemplateBase):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    
    provider: Optional[Dict[str, Any]] = None


# ===================== ЛОГИ ИСПОЛЬЗОВАНИЯ =====================

class AIUsageLogOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    user_id: Optional[int] = None
    provider_id: int
    task_type: str
    specialty: Optional[str] = None
    tokens_used: Optional[int] = None
    response_time_ms: Optional[int] = None
    success: bool
    error_message: Optional[str] = None
    cached_response: bool
    created_at: Optional[datetime] = None


# ===================== НАСТРОЙКИ AI СИСТЕМЫ =====================

class AISystemSettings(BaseModel):
    """Общие настройки AI системы"""
    enabled: bool = Field(True, description="Включена ли AI система")
    default_provider: str = Field("openai", description="Провайдер по умолчанию")
    fallback_chain: List[str] = Field(
        default=["openai", "gemini", "deepseek"], 
        description="Цепочка fallback провайдеров"
    )
    cache_enabled: bool = Field(True, description="Включено ли кэширование")
    cache_ttl_hours: int = Field(24, ge=1, le=168, description="TTL кэша в часах")
    
    # Глобальные лимиты
    global_limits: Dict[str, int] = Field(
        default={
            "requests_per_minute": 60,
            "tokens_per_day": 50000,
            "max_file_size_mb": 10
        },
        description="Глобальные лимиты системы"
    )
    
    # Настройки безопасности
    require_consent_for_files: bool = Field(True, description="Требовать согласие для обработки файлов")
    anonymize_data: bool = Field(True, description="Анонимизировать персональные данные")
    audit_all_requests: bool = Field(True, description="Логировать все запросы")


class AITestResult(BaseModel):
    """Результат тестирования AI провайдера"""
    success: bool
    response_text: Optional[str] = None
    response_time_ms: Optional[int] = None
    tokens_used: Optional[int] = None
    error_message: Optional[str] = None
    provider_info: Dict[str, Any] = {}


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
    by_provider: Dict[str, Dict[str, Any]]
    
    # По типам задач
    by_task_type: Dict[str, Dict[str, Any]]
    
    # По специальностям
    by_specialty: Dict[str, Dict[str, Any]]
    
    # За период
    period_start: datetime
    period_end: datetime

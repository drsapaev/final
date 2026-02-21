"""
Pydantic схемы для webhook'ов
"""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, HttpUrl, field_validator
from pydantic import ConfigDict

# ===================== БАЗОВЫЕ СХЕМЫ =====================


class WebhookEventTypeEnum(str, Enum):
    """Типы событий для webhook'ов"""

    # Пациенты
    PATIENT_CREATED = "patient.created"
    PATIENT_UPDATED = "patient.updated"
    PATIENT_DELETED = "patient.deleted"

    # Записи
    APPOINTMENT_CREATED = "appointment.created"
    APPOINTMENT_UPDATED = "appointment.updated"
    APPOINTMENT_CANCELLED = "appointment.cancelled"
    APPOINTMENT_COMPLETED = "appointment.completed"

    # Визиты
    VISIT_CREATED = "visit.created"
    VISIT_UPDATED = "visit.updated"
    VISIT_COMPLETED = "visit.completed"

    # Очереди
    QUEUE_ENTRY_CREATED = "queue.entry_created"
    QUEUE_ENTRY_UPDATED = "queue.entry_updated"
    QUEUE_ENTRY_CALLED = "queue.entry_called"
    QUEUE_ENTRY_COMPLETED = "queue.entry_completed"

    # Платежи
    PAYMENT_CREATED = "payment.created"
    PAYMENT_COMPLETED = "payment.completed"
    PAYMENT_FAILED = "payment.failed"
    PAYMENT_REFUNDED = "payment.refunded"

    # Пользователи
    USER_CREATED = "user.created"
    USER_UPDATED = "user.updated"
    USER_DELETED = "user.deleted"

    # Системные события
    SYSTEM_BACKUP_COMPLETED = "system.backup_completed"
    SYSTEM_BACKUP_FAILED = "system.backup_failed"
    SYSTEM_MAINTENANCE_START = "system.maintenance_start"
    SYSTEM_MAINTENANCE_END = "system.maintenance_end"


class WebhookStatusEnum(str, Enum):
    """Статусы webhook'ов"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    FAILED = "failed"


class WebhookCallStatusEnum(str, Enum):
    """Статусы вызовов webhook'ов"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


# ===================== WEBHOOK СХЕМЫ =====================


class WebhookBase(BaseModel):
    """Базовая схема webhook'а"""

    name: str
    description: str | None = None
    url: HttpUrl
    events: list[WebhookEventTypeEnum]
    headers: dict[str, str] | None = {}
    secret: str | None = None
    max_retries: int = 3
    retry_delay: int = 60
    timeout: int = 30
    filters: dict[str, Any] | None = {}

    @field_validator('events')
    @classmethod
    def validate_events(cls, v: list) -> list:
        if not v:
            raise ValueError('Необходимо указать хотя бы одно событие')
        return v

    @field_validator('max_retries')
    @classmethod
    def validate_max_retries(cls, v: int) -> int:
        if v < 0 or v > 10:
            raise ValueError('Количество повторов должно быть от 0 до 10')
        return v

    @field_validator('retry_delay')
    @classmethod
    def validate_retry_delay(cls, v: int) -> int:
        if v < 1 or v > 3600:
            raise ValueError('Задержка повтора должна быть от 1 до 3600 секунд')
        return v

    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        if v < 1 or v > 300:
            raise ValueError('Таймаут должен быть от 1 до 300 секунд')
        return v


class WebhookCreate(WebhookBase):
    """Схема для создания webhook'а"""

    pass


class WebhookUpdate(BaseModel):
    """Схема для обновления webhook'а"""

    name: str | None = None
    description: str | None = None
    url: HttpUrl | None = None
    events: list[WebhookEventTypeEnum] | None = None
    headers: dict[str, str] | None = None
    secret: str | None = None
    max_retries: int | None = None
    retry_delay: int | None = None
    timeout: int | None = None
    filters: dict[str, Any] | None = None
    status: WebhookStatusEnum | None = None
    is_active: bool | None = None


class WebhookInDB(WebhookBase):
    """Схема webhook'а в БД"""

    id: int
    uuid: str
    status: WebhookStatusEnum
    is_active: bool
    total_calls: int
    successful_calls: int
    failed_calls: int
    last_call_at: datetime | None = None
    last_success_at: datetime | None = None
    last_failure_at: datetime | None = None
    created_by: int | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class Webhook(WebhookInDB):
    """Публичная схема webhook'а"""

    pass


class WebhookWithStats(Webhook):
    """Webhook со статистикой"""

    success_rate: float
    recent_24h: dict[str, Any]


# ===================== WEBHOOK CALL СХЕМЫ =====================


class WebhookCallBase(BaseModel):
    """Базовая схема вызова webhook'а"""

    webhook_id: int
    event_type: WebhookEventTypeEnum
    event_data: dict[str, Any]
    url: HttpUrl
    method: str = "POST"
    headers: dict[str, str] | None = {}
    payload: dict[str, Any]


class WebhookCallCreate(WebhookCallBase):
    """Схема для создания вызова webhook'а"""

    max_attempts: int = 3


class WebhookCallInDB(WebhookCallBase):
    """Схема вызова webhook'а в БД"""

    id: int
    uuid: str
    status: WebhookCallStatusEnum
    response_status_code: int | None = None
    response_headers: dict[str, str] | None = {}
    response_body: str | None = None
    error_message: str | None = None
    attempt_number: int
    max_attempts: int
    next_retry_at: datetime | None = None
    duration_ms: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    completed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class WebhookCall(WebhookCallInDB):
    """Публичная схема вызова webhook'а"""

    pass


# ===================== WEBHOOK EVENT СХЕМЫ =====================


class WebhookEventBase(BaseModel):
    """Базовая схема события webhook'а"""

    event_type: WebhookEventTypeEnum
    event_data: dict[str, Any]
    source: str = "api"
    source_id: str | None = None
    correlation_id: str | None = None


class WebhookEventCreate(WebhookEventBase):
    """Схема для создания события webhook'а"""

    pass


class WebhookEventInDB(WebhookEventBase):
    """Схема события webhook'а в БД"""

    id: int
    uuid: str
    processed: bool
    processed_at: datetime | None = None
    failed_webhooks: list[str] = []
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WebhookEvent(WebhookEventInDB):
    """Публичная схема события webhook'а"""

    pass


# ===================== СТАТИСТИКА =====================


class WebhookStats(BaseModel):
    """Статистика webhook'а"""

    webhook_id: int
    name: str
    status: str
    total_calls: int
    successful_calls: int
    failed_calls: int
    success_rate: float
    last_call_at: str | None = None
    last_success_at: str | None = None
    last_failure_at: str | None = None
    recent_24h: dict[str, Any]


class SystemWebhookStats(BaseModel):
    """Общая статистика системы webhook'ов"""

    total_webhooks: int
    active_webhooks: int
    inactive_webhooks: int
    recent_24h: dict[str, Any]
    pending_retries: int
    unprocessed_events: int


# ===================== ТЕСТИРОВАНИЕ =====================


class WebhookTestRequest(BaseModel):
    """Запрос на тестирование webhook'а"""

    webhook_id: int
    event_type: WebhookEventTypeEnum
    test_data: dict[str, Any] | None = None


class WebhookTestResponse(BaseModel):
    """Ответ тестирования webhook'а"""

    success: bool
    status_code: int | None = None
    response_time_ms: int | None = None
    error_message: str | None = None
    call_id: int


# ===================== ФИЛЬТРЫ И ПОИСК =====================


class WebhookFilter(BaseModel):
    """Фильтры для поиска webhook'ов"""

    status: WebhookStatusEnum | None = None
    event_type: WebhookEventTypeEnum | None = None
    created_by: int | None = None
    name_contains: str | None = None
    url_contains: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


class WebhookCallFilter(BaseModel):
    """Фильтры для поиска вызовов webhook'ов"""

    webhook_id: int | None = None
    status: WebhookCallStatusEnum | None = None
    event_type: WebhookEventTypeEnum | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None
    min_duration_ms: int | None = None
    max_duration_ms: int | None = None


# ===================== ПАГИНАЦИЯ =====================


class WebhookListResponse(BaseModel):
    """Ответ со списком webhook'ов"""

    items: list[Webhook]
    total: int
    page: int
    size: int
    pages: int


class WebhookCallListResponse(BaseModel):
    """Ответ со списком вызовов webhook'ов"""

    items: list[WebhookCall]
    total: int
    page: int
    size: int
    pages: int


# ===================== УПРАВЛЕНИЕ =====================


class WebhookBulkAction(BaseModel):
    """Массовое действие над webhook'ами"""

    webhook_ids: list[int]
    action: str  # activate, deactivate, delete

    @field_validator('action')
    @classmethod
    def validate_action(cls, v: str) -> str:
        if v not in ['activate', 'deactivate', 'delete']:
            raise ValueError(
                'Действие должно быть одним из: activate, deactivate, delete'
            )
        return v


class WebhookBulkActionResponse(BaseModel):
    """Ответ на массовое действие"""

    success: bool
    processed: int
    failed: int
    errors: list[str] = []

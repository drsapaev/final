"""
Pydantic схемы для webhook'ов
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, HttpUrl, validator

from app.models.webhook import WebhookCallStatus, WebhookEventType, WebhookStatus

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
    description: Optional[str] = None
    url: HttpUrl
    events: List[WebhookEventTypeEnum]
    headers: Optional[Dict[str, str]] = {}
    secret: Optional[str] = None
    max_retries: int = 3
    retry_delay: int = 60
    timeout: int = 30
    filters: Optional[Dict[str, Any]] = {}

    @validator('events')
    def validate_events(cls, v):
        if not v:
            raise ValueError('Необходимо указать хотя бы одно событие')
        return v

    @validator('max_retries')
    def validate_max_retries(cls, v):
        if v < 0 or v > 10:
            raise ValueError('Количество повторов должно быть от 0 до 10')
        return v

    @validator('retry_delay')
    def validate_retry_delay(cls, v):
        if v < 1 or v > 3600:
            raise ValueError('Задержка повтора должна быть от 1 до 3600 секунд')
        return v

    @validator('timeout')
    def validate_timeout(cls, v):
        if v < 1 or v > 300:
            raise ValueError('Таймаут должен быть от 1 до 300 секунд')
        return v


class WebhookCreate(WebhookBase):
    """Схема для создания webhook'а"""

    pass


class WebhookUpdate(BaseModel):
    """Схема для обновления webhook'а"""

    name: Optional[str] = None
    description: Optional[str] = None
    url: Optional[HttpUrl] = None
    events: Optional[List[WebhookEventTypeEnum]] = None
    headers: Optional[Dict[str, str]] = None
    secret: Optional[str] = None
    max_retries: Optional[int] = None
    retry_delay: Optional[int] = None
    timeout: Optional[int] = None
    filters: Optional[Dict[str, Any]] = None
    status: Optional[WebhookStatusEnum] = None
    is_active: Optional[bool] = None


class WebhookInDB(WebhookBase):
    """Схема webhook'а в БД"""

    id: int
    uuid: str
    status: WebhookStatusEnum
    is_active: bool
    total_calls: int
    successful_calls: int
    failed_calls: int
    last_call_at: Optional[datetime] = None
    last_success_at: Optional[datetime] = None
    last_failure_at: Optional[datetime] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Webhook(WebhookInDB):
    """Публичная схема webhook'а"""

    pass


class WebhookWithStats(Webhook):
    """Webhook со статистикой"""

    success_rate: float
    recent_24h: Dict[str, Any]


# ===================== WEBHOOK CALL СХЕМЫ =====================


class WebhookCallBase(BaseModel):
    """Базовая схема вызова webhook'а"""

    webhook_id: int
    event_type: WebhookEventTypeEnum
    event_data: Dict[str, Any]
    url: HttpUrl
    method: str = "POST"
    headers: Optional[Dict[str, str]] = {}
    payload: Dict[str, Any]


class WebhookCallCreate(WebhookCallBase):
    """Схема для создания вызова webhook'а"""

    max_attempts: int = 3


class WebhookCallInDB(WebhookCallBase):
    """Схема вызова webhook'а в БД"""

    id: int
    uuid: str
    status: WebhookCallStatusEnum
    response_status_code: Optional[int] = None
    response_headers: Optional[Dict[str, str]] = {}
    response_body: Optional[str] = None
    error_message: Optional[str] = None
    attempt_number: int
    max_attempts: int
    next_retry_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    created_at: datetime
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class WebhookCall(WebhookCallInDB):
    """Публичная схема вызова webhook'а"""

    pass


# ===================== WEBHOOK EVENT СХЕМЫ =====================


class WebhookEventBase(BaseModel):
    """Базовая схема события webhook'а"""

    event_type: WebhookEventTypeEnum
    event_data: Dict[str, Any]
    source: str = "api"
    source_id: Optional[str] = None
    correlation_id: Optional[str] = None


class WebhookEventCreate(WebhookEventBase):
    """Схема для создания события webhook'а"""

    pass


class WebhookEventInDB(WebhookEventBase):
    """Схема события webhook'а в БД"""

    id: int
    uuid: str
    processed: bool
    processed_at: Optional[datetime] = None
    failed_webhooks: List[str] = []
    created_at: datetime

    class Config:
        from_attributes = True


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
    last_call_at: Optional[str] = None
    last_success_at: Optional[str] = None
    last_failure_at: Optional[str] = None
    recent_24h: Dict[str, Any]


class SystemWebhookStats(BaseModel):
    """Общая статистика системы webhook'ов"""

    total_webhooks: int
    active_webhooks: int
    inactive_webhooks: int
    recent_24h: Dict[str, Any]
    pending_retries: int
    unprocessed_events: int


# ===================== ТЕСТИРОВАНИЕ =====================


class WebhookTestRequest(BaseModel):
    """Запрос на тестирование webhook'а"""

    webhook_id: int
    event_type: WebhookEventTypeEnum
    test_data: Optional[Dict[str, Any]] = None


class WebhookTestResponse(BaseModel):
    """Ответ тестирования webhook'а"""

    success: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[int] = None
    error_message: Optional[str] = None
    call_id: int


# ===================== ФИЛЬТРЫ И ПОИСК =====================


class WebhookFilter(BaseModel):
    """Фильтры для поиска webhook'ов"""

    status: Optional[WebhookStatusEnum] = None
    event_type: Optional[WebhookEventTypeEnum] = None
    created_by: Optional[int] = None
    name_contains: Optional[str] = None
    url_contains: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


class WebhookCallFilter(BaseModel):
    """Фильтры для поиска вызовов webhook'ов"""

    webhook_id: Optional[int] = None
    status: Optional[WebhookCallStatusEnum] = None
    event_type: Optional[WebhookEventTypeEnum] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None
    min_duration_ms: Optional[int] = None
    max_duration_ms: Optional[int] = None


# ===================== ПАГИНАЦИЯ =====================


class WebhookListResponse(BaseModel):
    """Ответ со списком webhook'ов"""

    items: List[Webhook]
    total: int
    page: int
    size: int
    pages: int


class WebhookCallListResponse(BaseModel):
    """Ответ со списком вызовов webhook'ов"""

    items: List[WebhookCall]
    total: int
    page: int
    size: int
    pages: int


# ===================== УПРАВЛЕНИЕ =====================


class WebhookBulkAction(BaseModel):
    """Массовое действие над webhook'ами"""

    webhook_ids: List[int]
    action: str  # activate, deactivate, delete

    @validator('action')
    def validate_action(cls, v):
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
    errors: List[str] = []

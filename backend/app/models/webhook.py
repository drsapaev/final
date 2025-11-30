"""
Модели для системы webhook'ов
"""

import uuid
from enum import Enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
)
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class WebhookEventType(str, Enum):
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


class WebhookStatus(str, Enum):
    """Статусы webhook'ов"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    FAILED = "failed"


class WebhookCallStatus(str, Enum):
    """Статусы вызовов webhook'ов"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class Webhook(Base):
    """Модель webhook'а"""

    __tablename__ = "webhooks"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # Основная информация
    name = Column(String(255), nullable=False, index=True)
    description = Column(Text)
    url = Column(String(500), nullable=False)

    # Конфигурация
    events = Column(JSON, nullable=False)  # Список событий для подписки
    headers = Column(JSON, default={})  # Дополнительные заголовки
    secret = Column(String(255))  # Секрет для подписи

    # Настройки повторов
    max_retries = Column(Integer, default=3)
    retry_delay = Column(Integer, default=60)  # секунды
    timeout = Column(Integer, default=30)  # секунды

    # Фильтры
    filters = Column(JSON, default={})  # Условия для фильтрации событий

    # Статус
    status = Column(SQLEnum(WebhookStatus), default=WebhookStatus.ACTIVE, index=True)
    is_active = Column(Boolean, default=True, index=True)

    # Статистика
    total_calls = Column(Integer, default=0)
    successful_calls = Column(Integer, default=0)
    failed_calls = Column(Integer, default=0)
    last_call_at = Column(DateTime(timezone=True))
    last_success_at = Column(DateTime(timezone=True))
    last_failure_at = Column(DateTime(timezone=True))

    # Метаданные
    created_by = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    creator = relationship("User", back_populates="created_webhooks")
    calls = relationship(
        "WebhookCall", back_populates="webhook", cascade="all, delete-orphan"
    )


class WebhookCall(Base):
    """Модель вызова webhook'а"""

    __tablename__ = "webhook_calls"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # Связь с webhook'ом
    webhook_id = Column(Integer, ForeignKey("webhooks.id"), nullable=False, index=True)

    # Информация о событии
    event_type = Column(SQLEnum(WebhookEventType), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)

    # Информация о вызове
    url = Column(String(500), nullable=False)
    method = Column(String(10), default="POST")
    headers = Column(JSON, default={})
    payload = Column(JSON, nullable=False)

    # Результат
    status = Column(
        SQLEnum(WebhookCallStatus), default=WebhookCallStatus.PENDING, index=True
    )
    response_status_code = Column(Integer)
    response_headers = Column(JSON, default={})
    response_body = Column(Text)
    error_message = Column(Text)

    # Повторы
    attempt_number = Column(Integer, default=1)
    max_attempts = Column(Integer, default=3)
    next_retry_at = Column(DateTime(timezone=True))

    # Время выполнения
    duration_ms = Column(Integer)  # Время выполнения в миллисекундах

    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    completed_at = Column(DateTime(timezone=True))

    # Связи
    webhook = relationship("Webhook", back_populates="calls")


class WebhookEvent(Base):
    """Модель события для webhook'ов (очередь событий)"""

    __tablename__ = "webhook_events"

    id = Column(Integer, primary_key=True, index=True)
    uuid = Column(
        String(36), unique=True, index=True, default=lambda: str(uuid.uuid4())
    )

    # Информация о событии
    event_type = Column(SQLEnum(WebhookEventType), nullable=False, index=True)
    event_data = Column(JSON, nullable=False)

    # Метаданные события
    source = Column(String(100))  # Источник события (api, system, etc.)
    source_id = Column(String(100))  # ID источника
    correlation_id = Column(String(100))  # ID для корреляции событий

    # Статус обработки
    processed = Column(Boolean, default=False, index=True)
    processed_at = Column(DateTime(timezone=True))
    failed_webhooks = Column(
        JSON, default=[]
    )  # Список webhook'ов, которые не смогли обработать событие

    # Метаданные
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    # Индексы для быстрого поиска
    __table_args__ = {"extend_existing": True}


# Обновляем модель User для связи с webhook'ами
from app.models.user import User

User.created_webhooks = relationship("Webhook", back_populates="creator")

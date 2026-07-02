"""
Модели для системы webhook'ов
"""

from __future__ import annotations

import enum
import uuid as uuid_module
from datetime import datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy import Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class WebhookEventType(str, enum.Enum):
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


class WebhookStatus(str, enum.Enum):
    """Статусы webhook'ов"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    FAILED = "failed"


class WebhookCallStatus(str, enum.Enum):
    """Статусы вызовов webhook'ов"""

    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    CANCELLED = "cancelled"


class Webhook(Base):
    """Модель webhook'а"""

    __tablename__ = "webhooks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid_module.uuid4())
    )

    # Основная информация
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Конфигурация
    events: Mapped[list[str]] = mapped_column(JSON, nullable=False)  # Список событий для подписки
    headers: Mapped[dict[str, str]] = mapped_column(JSON, default={})  # Дополнительные заголовки
    secret: Mapped[str | None] = mapped_column(String(255))  # Секрет для подписи

    # Настройки повторов
    max_retries: Mapped[int] = mapped_column(Integer, default=3)
    retry_delay: Mapped[int] = mapped_column(Integer, default=60)  # секунды
    timeout: Mapped[int] = mapped_column(Integer, default=30)  # секунды

    # Фильтры
    filters: Mapped[dict[str, Any]] = mapped_column(JSON, default={})  # Условия для фильтрации событий

    # Статус
    status: Mapped[WebhookStatus] = mapped_column(
        SQLEnum(WebhookStatus), default=WebhookStatus.ACTIVE, index=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, index=True)

    # Статистика
    total_calls: Mapped[int] = mapped_column(Integer, default=0)
    successful_calls: Mapped[int] = mapped_column(Integer, default=0)
    failed_calls: Mapped[int] = mapped_column(Integer, default=0)
    last_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_failure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Метаданные
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"))
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Связи
    creator: Mapped[User | None] = relationship("User", back_populates="created_webhooks")
    calls: Mapped[list[WebhookCall]] = relationship(
        "WebhookCall", back_populates="webhook", cascade="all, delete-orphan"
    )


class WebhookCall(Base):
    """Модель вызова webhook'а"""

    __tablename__ = "webhook_calls"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid_module.uuid4())
    )

    # Связь с webhook'ом
    webhook_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("webhooks.id"), nullable=False, index=True
    )

    # Информация о событии
    event_type: Mapped[WebhookEventType] = mapped_column(
        SQLEnum(WebhookEventType), nullable=False, index=True
    )
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Информация о вызове
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    method: Mapped[str] = mapped_column(String(10), default="POST")
    headers: Mapped[dict[str, str]] = mapped_column(JSON, default={})
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Результат
    status: Mapped[WebhookCallStatus] = mapped_column(
        SQLEnum(WebhookCallStatus), default=WebhookCallStatus.PENDING, index=True
    )
    response_status_code: Mapped[int | None] = mapped_column(Integer)
    response_headers: Mapped[dict[str, str]] = mapped_column(JSON, default={})
    response_body: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)

    # Повторы
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Время выполнения
    duration_ms: Mapped[int | None] = mapped_column(Integer)  # Время выполнения в миллисекундах

    # Метаданные
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Связи
    webhook: Mapped[Webhook] = relationship("Webhook", back_populates="calls")


class WebhookEvent(Base):
    """Модель события для webhook'ов (очередь событий)"""

    __tablename__ = "webhook_events"
    __table_args__ = {"extend_existing": True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid_module.uuid4())
    )

    # Информация о событии
    event_type: Mapped[WebhookEventType] = mapped_column(
        SQLEnum(WebhookEventType), nullable=False, index=True
    )
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    # Метаданные события
    source: Mapped[str | None] = mapped_column(String(100))  # Источник события (api, system, etc.)
    source_id: Mapped[str | None] = mapped_column(String(100))  # ID источника
    correlation_id: Mapped[str | None] = mapped_column(String(100))  # ID для корреляции событий

    # Статус обработки
    processed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failed_webhooks: Mapped[list[int]] = mapped_column(
        JSON, default=[]
    )  # Список webhook'ов, которые не смогли обработать событие

    # Метаданные
    created_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# Обновляем модель User для связи с webhook'ами
from app.models.user import User  # noqa: E402

User.created_webhooks = relationship("Webhook", back_populates="creator")

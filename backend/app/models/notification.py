from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base_class import Base


def _uuid_str() -> str:
    return str(uuid.uuid4())


class NotificationEvent(Base):
    """Canonical notification event stored by the backend."""

    __tablename__ = "notification_events"
    __table_args__ = (
        UniqueConstraint("dedup_key", name="uq_notification_events_dedup_key"),
        Index("ix_notification_events_event_type_created_at", "event_type", "created_at"),
        Index("ix_notification_events_severity_created_at", "severity", "created_at"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    event_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False, default=_uuid_str
    )
    schema_version: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    correlation_id: Mapped[str | None] = mapped_column(
        String(36), nullable=True, index=True
    )
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    source_module: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    actor_role: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    entity_type: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    entity_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    severity: Mapped[str] = mapped_column(String(20), default="info", nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="normal", nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    payload_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    deep_link: Mapped[str | None] = mapped_column(String(500), nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    deliveries: Mapped[list[NotificationDelivery]] = relationship(
        "NotificationDelivery",
        back_populates="event",
        cascade="all, delete-orphan",
    )


class NotificationDelivery(Base):
    """Concrete delivery for a single recipient/channel."""

    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "recipient_id",
            "channel",
            "dedup_key",
            name="uq_notification_deliveries_recipient_channel_dedup",
        ),
        Index(
            "ix_notification_deliveries_recipient_sequence",
            "recipient_id",
            "sequence_id",
        ),
        Index(
            "ix_notification_deliveries_recipient_status",
            "recipient_id",
            "delivery_status",
        ),
        Index("ix_notification_deliveries_role_status", "role", "delivery_status"),
        Index(
            "ix_notification_deliveries_department_status",
            "department_key",
            "delivery_status",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    delivery_id: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, nullable=False, default=_uuid_str
    )
    event_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("notification_events.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    recipient_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    recipient_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    department_key: Mapped[str | None] = mapped_column(
        String(100), nullable=True, index=True
    )
    channel: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    dedup_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    sequence_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    delivery_status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False, index=True
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    first_delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    seen_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    read_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    payload_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

    event: Mapped[NotificationEvent] = relationship(
        "NotificationEvent", back_populates="deliveries"
    )


class NotificationTemplate(Base):
    """Шаблоны уведомлений"""

    __tablename__ = "notification_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Основная информация
    name: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # appointment_reminder, payment_success, etc.
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # email, sms, telegram

    # Шаблон
    subject: Mapped[str | None] = mapped_column(
        String(200), nullable=True
    )  # Для email
    template: Mapped[str] = mapped_column(Text, nullable=False)

    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )


class NotificationHistory(Base):
    """История отправленных уведомлений"""

    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Получатель
    recipient_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # patient, doctor, admin
    recipient_id: Mapped[int | None] = mapped_column(
        Integer, nullable=True, index=True
    )
    recipient_contact: Mapped[str] = mapped_column(
        String(255), nullable=False
    )  # email/phone

    # Уведомление
    notification_type: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )
    channel: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # email, sms, telegram
    template_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Содержание
    subject: Mapped[str | None] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)

    # Статус отправки
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, sent, failed, delivered
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Связанные данные
    related_entity_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # appointment, visit, payment
    related_entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    notification_metadata: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Временные метки
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)


class NotificationSettings(Base):
    """Настройки уведомлений пользователя"""

    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Пользователь
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_type: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # patient, doctor, admin

    # Каналы
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    push_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Типы уведомлений
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payment_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    queue_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Метаданные
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC), nullable=False
    )

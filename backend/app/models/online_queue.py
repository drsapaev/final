"""
Модели для онлайн-очереди согласно detail.md стр. 224-257

============================================================================
✅ OFFICIAL SSOT (Single Source of Truth) for Queue System
============================================================================

These models represent the OFFICIAL and PREFERRED queue system architecture:
  - DailyQueue: Specialist-based daily queues (SSOT)
  - OnlineQueueEntry: Queue entries with full metadata (SSOT)
  - QueueToken: QR code tokens for online registration (SSOT)

All NEW queue features MUST use these models.

DEPRECATED ALTERNATIVE:
  - app/models/online.py (OnlineDay) - legacy department-based system
  - app/services/online_queue.py - legacy service for appointments

See also:
  - docs/ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md (full specification)
  - docs/QUEUE_SYSTEM_ARCHITECTURE.md (architecture guide)
============================================================================
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.visit import Visit
    from app.models.user import User


class DailyQueue(Base):
    """Ежедневные очереди по специалистам"""

    __tablename__ = "daily_queues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)  # YYYY-MM-DD
    specialist_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("doctors.id"), nullable=False, index=True
    )  # ИСПРАВЛЕНО: FK к doctors.id
    queue_tag: Mapped[Optional[str]] = mapped_column(
        String(32), nullable=True, index=True
    )  # ecg, lab, cardiology_common, etc.
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opened_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Факт открытия приема

    # Информация о кабинете
    cabinet_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    cabinet_floor: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cabinet_building: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Временные ограничения для онлайн записи
    online_start_time: Mapped[str] = mapped_column(String(5), default="07:00", nullable=False)
    online_end_time: Mapped[str] = mapped_column(
        String(5), default="09:00", nullable=False
    )  # HH:MM или null если до opened_at
    max_online_entries: Mapped[int] = mapped_column(
        Integer, default=15, nullable=False
    )  # Максимум записей онлайн

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    specialist: Mapped["Doctor"] = relationship("Doctor", foreign_keys=[specialist_id])
    entries: Mapped[List["OnlineQueueEntry"]] = relationship(
        "OnlineQueueEntry", back_populates="queue", cascade="all, delete-orphan"
    )


class OnlineQueueEntry(Base):
    """Записи в онлайн-очереди"""

    __tablename__ = "queue_entries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    queue_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("daily_queues.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)  # Номер в очереди (1..N)

    # Идентификация пациента
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("patients.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve queue history for analytics and audit
    patient_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Если пациент не зарегистрирован
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)
    birth_year: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    address: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Связь с визитом (для подтвержденных визитов)
    visit_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("visits.id", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve queue history for analytics and audit

    # Тип визита и услуги
    visit_type: Mapped[str] = mapped_column(
        String(20), default="paid", nullable=False
    )  # paid, repeat, benefit
    discount_mode: Mapped[str] = mapped_column(
        String(20), default="none", nullable=False
    )  # none, repeat, benefit, all_free
    services: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )  # Список услуг с полными данными
    service_codes: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )  # DEPRECATED: Коды услуг ["K01", "K02", ...]
    total_amount: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Источник записи
    source: Mapped[str] = mapped_column(
        String(20), default="online", nullable=False
    )  # online, desk, telegram, confirmation, morning_assignment

    # Статус
    status: Mapped[str] = mapped_column(
        String(20), default="waiting", nullable=False
    )  # waiting, called, in_service, diagnostics, served, incomplete, no_show, cancelled

    # ✅ НОВОЕ: Дополнительные поля для статусов
    incomplete_reason: Mapped[Optional[str]] = mapped_column(
        String(200), nullable=True
    )  # Причина incomplete: "Пациент ушёл", "Не вернулся" и т.д.
    diagnostics_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )  # Время начала обследования (для таймера)

    # Время регистрации в очереди
    queue_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )

    # ✅ НОВОЕ: Приоритет (для вставки "следующим")
    priority: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # 0 = обычный, 1 = следующий (восстановленный), 2 = VIP

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    called_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    queue: Mapped["DailyQueue"] = relationship("DailyQueue", back_populates="entries")
    patient: Mapped[Optional["Patient"]] = relationship("Patient", foreign_keys=[patient_id])
    visit: Mapped[Optional["Visit"]] = relationship("Visit", foreign_keys=[visit_id])


class QueueToken(Base):
    """Токены для QR кодов очереди"""

    __tablename__ = "queue_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    token: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)

    # Параметры токена
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    specialist_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("doctors.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve queue tokens
    department: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, index=True)
    is_clinic_wide: Mapped[bool] = mapped_column(
        Boolean, default=False, nullable=False
    )  # True для общего QR клиники

    # Метаданные
    generated_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    usage_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Срок действия
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    specialist: Mapped[Optional["Doctor"]] = relationship("Doctor", foreign_keys=[specialist_id])
    generated_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[generated_by_user_id])


class QueueJoinSession(Base):
    """Сессии присоединения к очереди через QR"""

    __tablename__ = "queue_join_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Токен сессии
    session_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    # QR токен, по которому присоединились
    qr_token: Mapped[Optional[str]] = mapped_column(
        String(64), 
        ForeignKey("queue_tokens.token", ondelete="SET NULL"), 
        nullable=True, 
        index=True
    )  # ✅ SECURITY: SET NULL to preserve session history

    # Данные пациента
    patient_name: Mapped[str] = mapped_column(String(200), nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, index=True)

    # Статус сессии
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, joined, expired, cancelled

    # Результат присоединения
    queue_entry_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("queue_entries.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve session history
    queue_number: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # Метаданные
    user_agent: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    # Временные метки
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    joined_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # Relationships
    qr_token_rel: Mapped[Optional["QueueToken"]] = relationship(
        "QueueToken", foreign_keys=[qr_token]
    )
    queue_entry: Mapped[Optional["OnlineQueueEntry"]] = relationship(
        "OnlineQueueEntry", foreign_keys=[queue_entry_id]
    )


class QueueStatistics(Base):
    """Статистика очередей для аналитики"""

    __tablename__ = "queue_statistics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Привязка к очереди
    queue_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("daily_queues.id"), nullable=False, index=True
    )
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    # Статистика по источникам
    online_joins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Через QR
    desk_registrations: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Регистратор
    telegram_joins: Mapped[int] = mapped_column(Integer, default=0, nullable=False)  # Telegram бот
    confirmation_joins: Mapped[int] = mapped_column(
        Integer, default=0, nullable=False
    )  # Подтверждение визитов

    # Статистика по статусам
    total_served: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    total_no_show: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    average_wait_time: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # В минутах

    # Пиковые нагрузки
    peak_hour: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Час пик (0-23)
    max_queue_length: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Временные метки
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    # Relationships
    queue: Mapped["DailyQueue"] = relationship("DailyQueue", foreign_keys=[queue_id])

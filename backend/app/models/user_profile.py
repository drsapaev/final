"""
Расширенные модели для управления пользователями
"""

from __future__ import annotations

import enum
from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User


class UserStatus(str, enum.Enum):
    """Статусы пользователя"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    PENDING = "pending"
    LOCKED = "locked"


class UserProfile(Base):
    """Расширенный профиль пользователя"""

    __tablename__ = "user_profiles"
    __table_args__ = {'extend_existing': True}

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )  # ✅ SECURITY: CASCADE (profile dies with user)

    # Основная информация
    full_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    middle_name: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Контактная информация
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=False)
    alternative_email: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    # Личная информация
    date_of_birth: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)  # male, female, other
    nationality: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    language: Mapped[str] = mapped_column(String(10), default="ru")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")

    # Адрес
    address_line1: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    city: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    state: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    postal_code: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    country: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # Профессиональная информация
    job_title: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    employee_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    hire_date: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    salary: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # В копейках

    # Настройки
    avatar_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    website: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    social_links: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # {"linkedin": "...", "twitter": "..."}

    # Системная информация
    status: Mapped[UserStatus] = mapped_column(Enum(UserStatus), default=UserStatus.ACTIVE)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    login_count: Mapped[int] = mapped_column(Integer, default=0)
    failed_login_attempts: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="profile")
    preferences: Mapped[Optional["UserPreferences"]] = relationship(
        "UserPreferences",
        back_populates="profile",
        uselist=False,
        cascade="all, delete-orphan",
    )
    notifications: Mapped[Optional["UserNotificationSettings"]] = relationship(
        "UserNotificationSettings",
        back_populates="profile",
        uselist=False,
        cascade="all, delete-orphan",
    )


class UserPreferences(Base):
    """Настройки пользователя"""

    __tablename__ = "user_preferences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )  # ✅ SECURITY: CASCADE (profile dies with user)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id"), nullable=False, unique=True
    )

    # Общие настройки
    theme: Mapped[str] = mapped_column(String(20), default="light")  # light, dark, auto
    language: Mapped[str] = mapped_column(String(10), default="ru")
    timezone: Mapped[str] = mapped_column(String(50), default="Europe/Moscow")
    date_format: Mapped[str] = mapped_column(String(20), default="DD.MM.YYYY")
    time_format: Mapped[str] = mapped_column(String(10), default="24")  # 12, 24

    # Уведомления
    email_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    sms_notifications: Mapped[bool] = mapped_column(Boolean, default=False)
    push_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    desktop_notifications: Mapped[bool] = mapped_column(Boolean, default=True)

    # Рабочие настройки
    working_hours_start: Mapped[str] = mapped_column(String(5), default="09:00")
    working_hours_end: Mapped[str] = mapped_column(String(5), default="18:00")
    working_days: Mapped[Optional[List[int]]] = mapped_column(
        JSON, default=lambda: [1, 2, 3, 4, 5]
    )  # 1=Monday, 7=Sunday
    break_duration: Mapped[int] = mapped_column(Integer, default=60)  # В минутах

    # Интерфейс
    dashboard_layout: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    sidebar_collapsed: Mapped[bool] = mapped_column(Boolean, default=False)
    compact_mode: Mapped[bool] = mapped_column(Boolean, default=False)
    show_tooltips: Mapped[bool] = mapped_column(Boolean, default=True)

    # Безопасность
    session_timeout: Mapped[int] = mapped_column(Integer, default=30)  # В минутах
    require_2fa: Mapped[bool] = mapped_column(Boolean, default=False)
    auto_logout: Mapped[bool] = mapped_column(Boolean, default=True)

    # ============================================
    # EMR PREFERENCES (Smart Autocomplete)
    # ============================================
    # Режим умного поля (ghost | mvp | hybrid | word)
    emr_smart_field_mode: Mapped[str] = mapped_column(String(20), default="ghost")
    # Показывать переключатель режимов
    emr_show_mode_switcher: Mapped[bool] = mapped_column(Boolean, default=True)
    # Задержка debounce в мс
    emr_debounce_ms: Mapped[int] = mapped_column(Integer, default=500)
    # Недавно использованные коды МКБ-10 (массив кодов)
    emr_recent_icd10: Mapped[Optional[List[str]]] = mapped_column(
        JSON, default=lambda: []
    )  # ["I10", "I25.9", "E11.9"]
    # Недавно использованные шаблоны назначений
    emr_recent_templates: Mapped[Optional[List[str]]] = mapped_column(
        JSON, default=lambda: []
    )  # ["med-1", "exam-2"]
    # Избранные шаблоны по специальностям
    emr_favorite_templates: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, default=lambda: {}
    )  # {"cardiology": ["med-1"], "general": ["med-g1"]}
    # Кастомные шаблоны пользователя
    emr_custom_templates: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, default=lambda: []
    )  # [{"id": "custom-1", "name": "Мой шаблон", "template": "..."}]

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="preferences")
    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="preferences")


class UserNotificationSettings(Base):
    """Настройки уведомлений пользователя"""

    __tablename__ = "user_notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True
    )  # ✅ SECURITY: CASCADE (profile dies with user)
    profile_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user_profiles.id"), nullable=False, unique=True
    )

    # Email уведомления
    email_appointment_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    email_appointment_cancellation: Mapped[bool] = mapped_column(Boolean, default=True)
    email_appointment_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    email_payment_receipt: Mapped[bool] = mapped_column(Boolean, default=True)
    email_payment_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    email_system_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    email_security_alerts: Mapped[bool] = mapped_column(Boolean, default=True)
    email_newsletter: Mapped[bool] = mapped_column(Boolean, default=False)

    # SMS уведомления
    sms_appointment_reminder: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_appointment_cancellation: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_appointment_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_payment_receipt: Mapped[bool] = mapped_column(Boolean, default=False)
    sms_emergency: Mapped[bool] = mapped_column(Boolean, default=True)

    # Push уведомления
    push_appointment_reminder: Mapped[bool] = mapped_column(Boolean, default=True)
    push_appointment_cancellation: Mapped[bool] = mapped_column(Boolean, default=True)
    push_appointment_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    push_payment_receipt: Mapped[bool] = mapped_column(Boolean, default=True)
    push_system_updates: Mapped[bool] = mapped_column(Boolean, default=True)
    push_security_alerts: Mapped[bool] = mapped_column(Boolean, default=True)

    # Время уведомлений
    reminder_time_before: Mapped[int] = mapped_column(Integer, default=60)  # В минутах
    quiet_hours_start: Mapped[str] = mapped_column(String(5), default="22:00")
    quiet_hours_end: Mapped[str] = mapped_column(String(5), default="08:00")
    weekend_notifications: Mapped[bool] = mapped_column(Boolean, default=False)

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Связи
    user: Mapped["User"] = relationship("User", back_populates="notification_settings")
    profile: Mapped["UserProfile"] = relationship("UserProfile", back_populates="notifications")


# КРИТИЧЕСКИ ВАЖНО: Модели ролей УДАЛЕНЫ отсюда!
# Все модели ролей теперь ТОЛЬКО в app/models/role_permission.py
# Это предотвращает дублирование и конфликты таблиц


class UserAuditLog(Base):
    """Аудит действий пользователей - юридически обязательное логирование"""

    __tablename__ = "user_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True,
        index=True
    )  # ✅ FIX: SET NULL to preserve audit logs for compliance (legal requirement)

    # Действие
    action: Mapped[str] = mapped_column(
        String(50), nullable=False, index=True
    )  # CREATE, UPDATE, DELETE, LOGIN, LOGOUT, etc.
    resource_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )  # patients, visits, payments, emr, files, appointments, etc. (table_name)
    resource_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)  # row_id

    # Детали изменений
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    old_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Старые значения (для UPDATE/DELETE)
    new_values: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Новые значения (для CREATE/UPDATE)
    diff_hash: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)  # Хеш различий для быстрого сравнения

    # Контекст запроса
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True, index=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    session_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # Используется для request_id
    request_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)  # UUID запроса для трассировки

    # Метаданные
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )

    # Связи
    user: Mapped[Optional["User"]] = relationship("User", back_populates="audit_logs")

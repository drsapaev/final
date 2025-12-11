"""
Модели для конфигурации Telegram в админ панели
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.patient import Patient
    from app.models.user import User


class TelegramConfig(Base):
    """Конфигурация Telegram бота"""

    __tablename__ = "telegram_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bot_token: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Токен бота
    webhook_url: Mapped[Optional[str]] = mapped_column(String(300), nullable=True)  # URL вебхука
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Секрет для верификации

    # Настройки бота
    bot_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bot_name: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)

    # Чаты администраторов
    admin_chat_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)  # [123456, 789012]

    # Настройки уведомлений
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lab_results_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payment_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Языки
    default_language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)
    supported_languages: Mapped[List[str]] = mapped_column(
        JSON, default=["ru", "uz", "en"], nullable=False
    )

    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramTemplate(Base):
    """Шаблоны сообщений Telegram"""

    __tablename__ = "telegram_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    template_key: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # appointment_reminder, lab_ready
    template_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # notification, reminder, broadcast
    language: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)

    # Контент шаблона
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Заголовок (если нужен)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)  # Jinja2 шаблон сообщения

    # Настройки отправки
    parse_mode: Mapped[str] = mapped_column(
        String(20), default="HTML", nullable=False
    )  # HTML, Markdown, None
    disable_web_page_preview: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Кнопки (inline keyboard)
    inline_buttons: Mapped[Optional[List[Dict[str, Any]]]] = mapped_column(
        JSON, nullable=True
    )  # [{"text": "Подтвердить", "callback_data": "confirm"}]

    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramUser(Base):
    """Связка пользователей с Telegram"""

    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("patients.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve Telegram link
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve Telegram link

    # Telegram данные
    chat_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language_code: Mapped[str] = mapped_column(String(5), default="ru", nullable=False)

    # Настройки уведомлений
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    lab_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # Статус
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    blocked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)  # Заблокировал бота
    last_activity: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    patient: Mapped[Optional["Patient"]] = relationship("Patient", foreign_keys=[patient_id])
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])


class TelegramMessage(Base):
    """Лог отправленных сообщений"""

    __tablename__ = "telegram_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    chat_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    message_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # ID сообщения в Telegram

    # Тип и контент
    message_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # reminder, notification, broadcast
    template_key: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)

    # Статус доставки
    status: Mapped[str] = mapped_column(
        String(20), default="pending", nullable=False
    )  # pending, sent, delivered, failed
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Метаданные
    sent_by_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve message log
    related_entity_type: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True
    )  # appointment, visit, payment
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    sent_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[sent_by_user_id])

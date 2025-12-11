"""
Модели для Telegram интеграции
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from app.db.base_class import Base


class TelegramConfig(Base):
    """Конфигурация Telegram бота"""

    __tablename__ = "telegram_configs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    bot_token: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    webhook_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    webhook_secret: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bot_username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    bot_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    admin_chat_ids: Mapped[Optional[List[int]]] = mapped_column(JSON, nullable=True)  # Список ID админских чатов
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True)
    lab_results_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    payment_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    default_language: Mapped[str] = mapped_column(String(10), default="ru")
    supported_languages: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Список поддерживаемых языков
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramUser(Base):
    """Пользователи Telegram"""

    __tablename__ = "telegram_users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_id: Mapped[int] = mapped_column(Integer, unique=True, nullable=False, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    last_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    language_code: Mapped[str] = mapped_column(String(10), default="ru")
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notifications_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class TelegramMessage(Base):
    """Сообщения Telegram"""

    __tablename__ = "telegram_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    telegram_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # appointment_reminder, lab_result, etc.
    message_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    message_data: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Дополнительные данные
    sent_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    status: Mapped[str] = mapped_column(String(20), default="sent")  # sent, failed, pending
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

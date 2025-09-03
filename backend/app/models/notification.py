from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, Integer, String, Text, Boolean, JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base_class import Base


class NotificationTemplate(Base):
    """Шаблоны уведомлений"""
    __tablename__ = "notification_templates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Основная информация
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True, index=True)
    type: Mapped[str] = mapped_column(String(50), nullable=False)  # appointment_reminder, payment_success, etc.
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # email, sms, telegram
    
    # Шаблон
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)  # Для email
    template: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Статус
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class NotificationHistory(Base):
    """История отправленных уведомлений"""
    __tablename__ = "notification_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Получатель
    recipient_type: Mapped[str] = mapped_column(String(20), nullable=False)  # patient, doctor, admin
    recipient_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, index=True)
    recipient_contact: Mapped[str] = mapped_column(String(255), nullable=False)  # email/phone
    
    # Уведомление
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # email, sms, telegram
    template_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Содержание
    subject: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Статус отправки
    status: Mapped[str] = mapped_column(String(20), default="pending", nullable=False)  # pending, sent, failed, delivered
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Связанные данные
    related_entity_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # appointment, visit, payment
    related_entity_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    notification_metadata: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    
    # Временные метки
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class NotificationSettings(Base):
    """Настройки уведомлений для пользователей"""
    __tablename__ = "notification_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    
    # Пользователь
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    user_type: Mapped[str] = mapped_column(String(20), nullable=False)  # patient, doctor, admin
    
    # Настройки каналов
    email_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    sms_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    telegram_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Настройки типов уведомлений
    appointment_reminders: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    payment_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    queue_updates: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    system_alerts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Расписание уведомлений
    reminder_hours_before: Mapped[int] = mapped_column(Integer, default=24, nullable=False)  # За сколько часов напоминать
    
    # Контакты для уведомлений
    notification_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    notification_phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    telegram_chat_id: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    
    # Метаданные
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

"""
Модели для Telegram интеграции
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.sql import func
from app.db.base_class import Base


class TelegramConfig(Base):
    """Конфигурация Telegram бота"""
    __tablename__ = "telegram_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_token = Column(String(255), nullable=True)
    webhook_url = Column(String(500), nullable=True)
    webhook_secret = Column(String(255), nullable=True)
    bot_username = Column(String(100), nullable=True)
    bot_name = Column(String(100), nullable=True)
    admin_chat_ids = Column(JSON, nullable=True)  # Список ID админских чатов
    notifications_enabled = Column(Boolean, default=True)
    appointment_reminders = Column(Boolean, default=True)
    lab_results_notifications = Column(Boolean, default=True)
    payment_notifications = Column(Boolean, default=True)
    default_language = Column(String(10), default="ru")
    supported_languages = Column(JSON, nullable=True)  # Список поддерживаемых языков
    active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TelegramUser(Base):
    """Пользователи Telegram"""
    __tablename__ = "telegram_users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    language_code = Column(String(10), default="ru")
    is_bot = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    notifications_enabled = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TelegramMessage(Base):
    """Сообщения Telegram"""
    __tablename__ = "telegram_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_user_id = Column(Integer, nullable=False, index=True)
    message_type = Column(String(50), nullable=False)  # appointment_reminder, lab_result, etc.
    message_text = Column(Text, nullable=True)
    message_data = Column(JSON, nullable=True)  # Дополнительные данные
    sent_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="sent")  # sent, failed, pending
    error_message = Column(Text, nullable=True)

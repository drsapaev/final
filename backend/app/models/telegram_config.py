"""
Модели для конфигурации Telegram в админ панели
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, JSON, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class TelegramConfig(Base):
    """Конфигурация Telegram бота"""
    __tablename__ = "telegram_configs"
    
    id = Column(Integer, primary_key=True, index=True)
    bot_token = Column(String(200), nullable=True)  # Токен бота
    webhook_url = Column(String(300), nullable=True)  # URL вебхука
    webhook_secret = Column(String(100), nullable=True)  # Секрет для верификации
    
    # Настройки бота
    bot_username = Column(String(100), nullable=True)
    bot_name = Column(String(150), nullable=True)
    
    # Чаты администраторов
    admin_chat_ids = Column(JSON, nullable=True)  # [123456, 789012]
    
    # Настройки уведомлений
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    appointment_reminders = Column(Boolean, default=True, nullable=False)
    lab_results_notifications = Column(Boolean, default=True, nullable=False)
    payment_notifications = Column(Boolean, default=True, nullable=False)
    
    # Языки
    default_language = Column(String(5), default="ru", nullable=False)
    supported_languages = Column(JSON, default=["ru", "uz", "en"], nullable=False)
    
    active = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TelegramTemplate(Base):
    """Шаблоны сообщений Telegram"""
    __tablename__ = "telegram_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    template_key = Column(String(100), nullable=False, index=True)  # appointment_reminder, lab_ready
    template_type = Column(String(50), nullable=False)  # notification, reminder, broadcast
    language = Column(String(5), default="ru", nullable=False)
    
    # Контент шаблона
    subject = Column(String(200), nullable=True)  # Заголовок (если нужен)
    message_text = Column(Text, nullable=False)  # Jinja2 шаблон сообщения
    
    # Настройки отправки
    parse_mode = Column(String(20), default="HTML", nullable=False)  # HTML, Markdown, None
    disable_web_page_preview = Column(Boolean, default=True, nullable=False)
    
    # Кнопки (inline keyboard)
    inline_buttons = Column(JSON, nullable=True)  # [{"text": "Подтвердить", "callback_data": "confirm"}]
    
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class TelegramUser(Base):
    """Связка пользователей с Telegram"""
    __tablename__ = "telegram_users"
    
    id = Column(Integer, primary_key=True, index=True)
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)  # Для персонала
    
    # Telegram данные
    chat_id = Column(BigInteger, unique=True, nullable=False, index=True)
    username = Column(String(100), nullable=True)
    first_name = Column(String(100), nullable=True)
    last_name = Column(String(100), nullable=True)
    language_code = Column(String(5), default="ru", nullable=False)
    
    # Настройки уведомлений
    notifications_enabled = Column(Boolean, default=True, nullable=False)
    appointment_reminders = Column(Boolean, default=True, nullable=False)
    lab_notifications = Column(Boolean, default=True, nullable=False)
    
    # Статус
    active = Column(Boolean, default=True, nullable=False)
    blocked = Column(Boolean, default=False, nullable=False)  # Заблокировал бота
    last_activity = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    patient = relationship("Patient", foreign_keys=[patient_id])
    user = relationship("User", foreign_keys=[user_id])


class TelegramMessage(Base):
    """Лог отправленных сообщений"""
    __tablename__ = "telegram_messages"
    
    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, nullable=False, index=True)
    message_id = Column(Integer, nullable=True)  # ID сообщения в Telegram
    
    # Тип и контент
    message_type = Column(String(50), nullable=False)  # reminder, notification, broadcast
    template_key = Column(String(100), nullable=True)
    message_text = Column(Text, nullable=False)
    
    # Статус доставки
    status = Column(String(20), default="pending", nullable=False)  # pending, sent, delivered, failed
    error_message = Column(Text, nullable=True)
    
    # Метаданные
    sent_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    related_entity_type = Column(String(50), nullable=True)  # appointment, visit, payment
    related_entity_id = Column(Integer, nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    sent_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    sent_by = relationship("User", foreign_keys=[sent_by_user_id])

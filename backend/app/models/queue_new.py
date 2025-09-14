"""
Модели для системы очередей
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Text, Date
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
import uuid
from sqlalchemy.dialects.postgresql import UUID


class DailyQueue(Base):
    """
    Ежедневная очередь для каждого специалиста
    """
    __tablename__ = "daily_queues_new"

    id = Column(Integer, primary_key=True, index=True)
    day = Column(Date, nullable=False, index=True)  # Дата очереди
    specialist_id = Column(Integer, ForeignKey("users.id"), nullable=False)  # ID врача
    active = Column(Boolean, default=True)  # Активна ли очередь
    opened_at = Column(DateTime, nullable=True)  # Время открытия приема (закрывает онлайн-запись)
    created_at = Column(DateTime, server_default=func.now())
    
    # Настройки очереди
    max_online_slots = Column(Integer, default=15)  # Максимум мест для онлайн-записи
    start_number = Column(Integer, default=1)  # Стартовый номер для специальности
    auto_close_time = Column(String(5), default="09:00")  # Время автозакрытия (HH:MM)
    
    # Связи
    specialist = relationship("User")
    entries = relationship("QueueEntryNew", back_populates="queue", cascade="all, delete-orphan")


class QueueEntryNew(Base):
    """
    Запись в очереди (один пациент)
    """
    __tablename__ = "queue_entries_new"

    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("daily_queues_new.id"), nullable=False)
    number = Column(Integer, nullable=False)  # Номер в очереди
    
    # Данные пациента
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)  # Если зарегистрированный
    patient_name = Column(String(255), nullable=True)  # ФИО (для незарегистрированных)
    phone = Column(String(20), nullable=True, index=True)  # Телефон
    telegram_id = Column(String(50), nullable=True, index=True)  # Telegram ID
    
    # Метаданные
    source = Column(String(20), default="online")  # online, desk, telegram
    status = Column(String(20), default="waiting")  # waiting, called, completed, cancelled
    created_at = Column(DateTime, server_default=func.now())
    called_at = Column(DateTime, nullable=True)  # Время вызова
    
    # Связи
    queue = relationship("DailyQueue", back_populates="entries")
    # patient = relationship("Patient", back_populates="queue_entries")  # Временно отключено


class QueueToken(Base):
    """
    Токены для QR кодов (временные ссылки)
    """
    __tablename__ = "queue_tokens_new"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(255), unique=True, index=True, nullable=False)  # UUID токен
    day = Column(Date, nullable=False)  # На какой день
    specialist_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Настройки токена
    expires_at = Column(DateTime, nullable=False)  # Время истечения
    max_uses = Column(Integer, default=50)  # Максимум использований
    current_uses = Column(Integer, default=0)  # Текущее количество использований
    
    created_at = Column(DateTime, server_default=func.now())
    
    # Связи
    specialist = relationship("User")


# Добавляем связи в существующие модели - ВРЕМЕННО ОТКЛЮЧЕНО
# def add_queue_relationships():
#     """
#     Добавляет связи очередей к существующим моделям
#     Вызывается после импорта всех моделей
#     """
#     from app.models.user import User
#     # from app.models.patient import Patient
#     
#     # Добавляем связи к User
#     if not hasattr(User, 'daily_queues'):
#         User.daily_queues = relationship("DailyQueue", back_populates="specialist")
#     
#     # Добавляем связи к Patient
#     # if not hasattr(Patient, 'queue_entries'):
#     #     Patient.queue_entries = relationship("QueueEntry", back_populates="patient")
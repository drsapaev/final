"""
Модели для онлайн-очереди согласно detail.md стр. 224-257
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Date, BigInteger
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class DailyQueue(Base):
    """Ежедневные очереди по специалистам"""
    __tablename__ = "daily_queues"
    
    id = Column(Integer, primary_key=True, index=True)
    day = Column(Date, nullable=False, index=True)  # YYYY-MM-DD
    specialist_id = Column(Integer, ForeignKey("doctors.id"), nullable=False, index=True)
    active = Column(Boolean, default=True, nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=True)  # Факт открытия приема
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    specialist = relationship("Doctor", foreign_keys=[specialist_id])
    entries = relationship("QueueEntry", back_populates="queue", cascade="all, delete-orphan")


class QueueEntry(Base):
    """Записи в онлайн-очереди"""
    __tablename__ = "queue_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    queue_id = Column(Integer, ForeignKey("daily_queues.id", ondelete="CASCADE"), nullable=False, index=True)
    number = Column(Integer, nullable=False, index=True)  # Номер в очереди (1..N)
    
    # Идентификация пациента
    patient_id = Column(Integer, ForeignKey("patients.id"), nullable=True)
    patient_name = Column(String(200), nullable=True)  # Если пациент не зарегистрирован
    phone = Column(String(20), nullable=True, index=True)  # Для уникальности
    telegram_id = Column(BigInteger, nullable=True, index=True)  # Для уникальности
    
    # Источник записи
    source = Column(String(20), default="online", nullable=False)  # online, desk, telegram
    
    # Статус
    status = Column(String(20), default="waiting", nullable=False)  # waiting, called, served, no_show
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    called_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    queue = relationship("DailyQueue", back_populates="entries")
    patient = relationship("Patient", foreign_keys=[patient_id])


class QueueToken(Base):
    """Токены для QR кодов очереди"""
    __tablename__ = "queue_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(100), unique=True, nullable=False, index=True)
    
    # Параметры токена
    day = Column(Date, nullable=False, index=True)
    specialist_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    
    # Метаданные
    generated_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    usage_count = Column(Integer, default=0, nullable=False)  # Сколько раз использован
    
    # Срок действия
    expires_at = Column(DateTime(timezone=True), nullable=False)
    active = Column(Boolean, default=True, nullable=False)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    specialist = relationship("Doctor", foreign_keys=[specialist_id])
    generated_by = relationship("User", foreign_keys=[generated_by_user_id])

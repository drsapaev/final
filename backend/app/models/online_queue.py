"""
Модели для онлайн-очереди согласно detail.md стр. 224-257
"""
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey, Date, BigInteger, Text, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class DailyQueue(Base):
    """Ежедневные очереди по специалистам"""
    __tablename__ = "daily_queues"
    
    id = Column(Integer, primary_key=True, index=True)
    day = Column(Date, nullable=False, index=True)  # YYYY-MM-DD
    specialist_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    queue_tag = Column(String(32), nullable=True, index=True)  # ecg, lab, cardiology_common, etc.
    active = Column(Boolean, default=True, nullable=False)
    opened_at = Column(DateTime(timezone=True), nullable=True)  # Факт открытия приема
    
    # Временные ограничения для онлайн записи
    online_start_time = Column(String(5), default="07:00", nullable=False)  # HH:MM
    online_end_time = Column(String(5), default="09:00", nullable=False)    # HH:MM или null если до opened_at
    max_online_entries = Column(Integer, default=15, nullable=False)        # Максимум записей онлайн
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    specialist = relationship("User", foreign_keys=[specialist_id])
    entries = relationship("OnlineQueueEntry", back_populates="queue", cascade="all, delete-orphan")


class OnlineQueueEntry(Base):
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
    
    # Связь с визитом (для подтвержденных визитов)
    visit_id = Column(Integer, ForeignKey("visits.id"), nullable=True, index=True)
    
    # Источник записи
    source = Column(String(20), default="online", nullable=False)  # online, desk, telegram, confirmation, morning_assignment
    
    # Статус
    status = Column(String(20), default="waiting", nullable=False)  # waiting, called, served, no_show
    
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    called_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relationships
    queue = relationship("DailyQueue", back_populates="entries")
    patient = relationship("Patient", foreign_keys=[patient_id])
    visit = relationship("Visit", foreign_keys=[visit_id])


class QueueToken(Base):
    """Токены для QR кодов очереди"""
    __tablename__ = "queue_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    token = Column(String(100), unique=True, nullable=False, index=True)
    
    # Параметры токена
    day = Column(Date, nullable=False, index=True)
    specialist_id = Column(Integer, ForeignKey("doctors.id"), nullable=False)
    department = Column(String(50), nullable=True, index=True)  # Отделение
    
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


class QueueJoinSession(Base):
    """Сессии присоединения к очереди через QR"""
    __tablename__ = "queue_join_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Токен сессии
    session_token = Column(String(64), unique=True, nullable=False, index=True)
    
    # QR токен, по которому присоединились
    qr_token = Column(String(64), ForeignKey("queue_tokens.token"), nullable=False, index=True)
    
    # Данные пациента
    patient_name = Column(String(200), nullable=False)
    phone = Column(String(20), nullable=False, index=True)
    telegram_id = Column(BigInteger, nullable=True, index=True)
    
    # Статус сессии
    status = Column(String(20), default="pending", nullable=False)  # pending, joined, expired, cancelled
    
    # Результат присоединения
    queue_entry_id = Column(Integer, ForeignKey("queue_entries.id"), nullable=True)
    queue_number = Column(Integer, nullable=True)
    
    # Метаданные
    user_agent = Column(String(500), nullable=True)
    ip_address = Column(String(45), nullable=True)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    joined_at = Column(DateTime(timezone=True), nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    
    # Relationships
    qr_token_rel = relationship("QueueToken", foreign_keys=[qr_token])
    queue_entry = relationship("OnlineQueueEntry", foreign_keys=[queue_entry_id])


class QueueStatistics(Base):
    """Статистика очередей для аналитики"""
    __tablename__ = "queue_statistics"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Привязка к очереди
    queue_id = Column(Integer, ForeignKey("daily_queues.id"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    
    # Статистика по источникам
    online_joins = Column(Integer, default=0, nullable=False)  # Через QR
    desk_registrations = Column(Integer, default=0, nullable=False)  # Регистратор
    telegram_joins = Column(Integer, default=0, nullable=False)  # Telegram бот
    confirmation_joins = Column(Integer, default=0, nullable=False)  # Подтверждение визитов
    
    # Статистика по статусам
    total_served = Column(Integer, default=0, nullable=False)
    total_no_show = Column(Integer, default=0, nullable=False)
    average_wait_time = Column(Integer, nullable=True)  # В минутах
    
    # Пиковые нагрузки
    peak_hour = Column(Integer, nullable=True)  # Час пик (0-23)
    max_queue_length = Column(Integer, default=0, nullable=False)
    
    # Временные метки
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships
    queue = relationship("DailyQueue", foreign_keys=[queue_id])

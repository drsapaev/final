"""
Модели для управления клиникой в админ панели
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Time, Numeric, JSON
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base


class ClinicSettings(Base):
    """Настройки клиники"""
    __tablename__ = "clinic_settings"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    category = Column(String(50), nullable=True, index=True)  # clinic, queue, ai, print, telegram
    description = Column(Text, nullable=True)
    updated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    updated_by_user = relationship("User", foreign_keys=[updated_by])


class Doctor(Base):
    """Врачи клиники"""
    __tablename__ = "doctors"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    specialty = Column(String(100), nullable=False, index=True)  # cardiology, dermatology, stomatology
    cabinet = Column(String(20), nullable=True)
    price_default = Column(Numeric(10, 2), nullable=True)
    start_number_online = Column(Integer, default=1, nullable=False)
    max_online_per_day = Column(Integer, default=15, nullable=False)
    auto_close_time = Column(Time, default="09:00", nullable=True)
    active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User", foreign_keys=[user_id])
    schedules = relationship("Schedule", back_populates="doctor", cascade="all, delete-orphan")
    services = relationship("Service", back_populates="doctor")


class Schedule(Base):
    """Расписание врачей"""
    __tablename__ = "schedules"
    
    id = Column(Integer, primary_key=True, index=True)
    doctor_id = Column(Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False)
    weekday = Column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time = Column(Time, nullable=True)
    end_time = Column(Time, nullable=True)
    breaks = Column(JSON, nullable=True)  # [{"start": "12:00", "end": "13:00"}]
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    doctor = relationship("Doctor", back_populates="schedules")


class ServiceCategory(Base):
    """Категории услуг"""
    __tablename__ = "service_categories"
    
    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False)
    name_ru = Column(String(100), nullable=True)
    name_uz = Column(String(100), nullable=True)
    name_en = Column(String(100), nullable=True)
    specialty = Column(String(100), nullable=True, index=True)
    active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    services = relationship("Service", back_populates="category")

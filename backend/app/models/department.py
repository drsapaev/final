"""
Department model for managing clinic departments/tabs
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean, Column, Integer, String, Text,
    DateTime, ForeignKey, Numeric, UniqueConstraint
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base


class Department(Base):
    """
    Модель отделения клиники

    Представляет вкладку/отделение в панели регистратора:
    - cardio (Кардиология)
    - echokg (ЭКГ)
    - derma (Дерматология)
    - dental (Стоматология)
    - lab (Лаборатория)
    - procedures (Процедуры)
    """
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    # Уникальный ключ отделения (cardio, echokg, derma, dental, lab, procedures)
    key: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)

    # Название отделения (русский)
    name_ru: Mapped[str] = mapped_column(String(200), nullable=False)

    # Название отделения (узбекский)
    name_uz: Mapped[str] = mapped_column(String(200), nullable=True)

    # Иконка (lucide-react icon name)
    icon: Mapped[str] = mapped_column(String(50), nullable=True, default="folder")

    # Цвет для UI
    color: Mapped[str] = mapped_column(String(50), nullable=True)

    # Градиент для UI
    gradient: Mapped[str] = mapped_column(Text, nullable=True)

    # Порядок отображения
    display_order: Mapped[int] = mapped_column(Integer, default=999)

    # Активность отделения
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Описание
    description: Mapped[str] = mapped_column(Text, nullable=True)

    # ==================== RELATIONSHIPS ====================
    # Привязка услуг к отделению (Many-to-Many с атрибутами)
    services: Mapped[list["DepartmentService"]] = relationship(
        back_populates="department", cascade="all, delete-orphan"
    )

    # Врачи отделения (One-to-Many)
    doctors: Mapped[list["Doctor"]] = relationship(
        back_populates="department"
    )

    # Записи в отделение (One-to-Many)
    appointments: Mapped[list["Appointment"]] = relationship(
        back_populates="department"
    )

    # Визиты в отделение (One-to-Many)
    visits: Mapped[list["Visit"]] = relationship(
        back_populates="department"
    )

    # Расписания отделения (One-to-Many)
    schedules: Mapped[list["ScheduleTemplate"]] = relationship(
        back_populates="department"
    )

    # Настройки очереди (One-to-One)
    queue_settings: Mapped["DepartmentQueueSettings"] = relationship(
        back_populates="department", uselist=False, cascade="all, delete-orphan"
    )

    # Настройки регистрации (One-to-One)
    registration_settings: Mapped["DepartmentRegistrationSettings"] = relationship(
        back_populates="department", uselist=False, cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Department(key='{self.key}', name_ru='{self.name_ru}', active={self.active})>"


# ============================================================
# DEPARTMENT SERVICES (Many-to-Many с атрибутами)
# ============================================================

class DepartmentService(Base):
    """
    Связь отделения с услугами (Many-to-Many с атрибутами)

    Позволяет:
    - Привязывать услуги к отделениям
    - Переопределять цены для услуг в отделении
    - Устанавливать дефолтные услуги
    - Задавать порядок отображения
    """
    __tablename__ = "department_services"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    service_id: Mapped[int] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"),
        nullable=False, index=True
    )

    # Дефолтная услуга для отделения
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)

    # Порядок отображения
    display_order: Mapped[int] = mapped_column(Integer, default=999)

    # Переопределение цены (если нужна особая цена для отделения)
    price_override: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    department: Mapped[Department] = relationship(back_populates="services")
    service: Mapped["Service"] = relationship()

    __table_args__ = (
        UniqueConstraint("department_id", "service_id",
            name="uq_department_service"),
    )

    def __repr__(self):
        return f"<DepartmentService(dept_id={self.department_id}, service_id={self.service_id})>"


# ============================================================
# DEPARTMENT QUEUE SETTINGS (One-to-One)
# ============================================================

class DepartmentQueueSettings(Base):
    """
    Настройки очереди для отделения (One-to-One)

    Управляет:
    - Типом очереди (живая/онлайн/смешанная)
    - Лимитами очереди
    - Префиксами номеров
    - Временем закрытия
    """
    __tablename__ = "department_queue_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )

    # Включена ли очередь
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    # Тип очереди: 'live', 'online', 'mixed'
    queue_type: Mapped[str] = mapped_column(
        String(20), default="mixed"
    )

    # Префикс номера очереди (К-, Д-, Л-)
    queue_prefix: Mapped[str] = mapped_column(
        String(10), nullable=True
    )

    # Максимум записей в день
    max_daily_queue: Mapped[int] = mapped_column(Integer, default=50)

    # Максимум одновременных записей
    max_concurrent_queue: Mapped[int] = mapped_column(Integer, default=15)

    # Среднее время ожидания (минуты)
    avg_wait_time: Mapped[int] = mapped_column(
        Integer, default=20
    )

    # Показывать на табло
    show_on_display: Mapped[bool] = mapped_column(Boolean, default=True)

    # Время авто-закрытия очереди (HH:MM)
    auto_close_time: Mapped[str] = mapped_column(
        String(5), default="09:00"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationship
    department: Mapped[Department] = relationship(
        back_populates="queue_settings"
    )

    def __repr__(self):
        return f"<DepartmentQueueSettings(dept_id={self.department_id}, type={self.queue_type})>"


# ============================================================
# DEPARTMENT REGISTRATION SETTINGS (One-to-One)
# ============================================================

class DepartmentRegistrationSettings(Base):
    """
    Настройки регистрации для отделения (One-to-One)

    Управляет:
    - Онлайн-записью
    - Подтверждением записей
    - Временными лимитами записи
    - Авто-назначением врачей
    """
    __tablename__ = "department_registration_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)

    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"),
        nullable=False, unique=True, index=True
    )

    # Разрешена ли онлайн-запись
    online_booking_enabled: Mapped[bool] = mapped_column(
        Boolean, default=True
    )

    # Требуется ли подтверждение записи
    requires_confirmation: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    # За сколько часов минимум можно записаться
    min_booking_hours: Mapped[int] = mapped_column(
        Integer, default=2
    )

    # На сколько дней вперед можно записаться
    max_booking_days: Mapped[int] = mapped_column(
        Integer, default=30
    )

    # Авто-назначать врача при записи
    auto_assign_doctor: Mapped[bool] = mapped_column(
        Boolean, default=False
    )

    # Разрешить приход без записи (walk-in)
    allow_walkin: Mapped[bool] = mapped_column(
        Boolean, default=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now()
    )

    # Relationship
    department: Mapped[Department] = relationship(
        back_populates="registration_settings"
    )

    def __repr__(self):
        return f"<DepartmentRegistrationSettings(dept_id={self.department_id}, online={self.online_booking_enabled})>"

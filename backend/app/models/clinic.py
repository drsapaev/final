"""
Модели для управления клиникой в админ панели
"""

from __future__ import annotations

import enum
from datetime import date, datetime, time
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.sql import func

from app.db.base_class import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.department import Department
    from app.models.service import Service
    from app.models.visit import Visit
    from app.models.doctor_price_override import DoctorPriceOverride


class ClinicSettings(Base):
    """Настройки клиники"""

    __tablename__ = "clinic_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(
        String(50), nullable=True, index=True
    )  # clinic, queue, ai, print, telegram
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    updated_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[updated_by])


class Doctor(Base):
    """Врачи клиники"""

    __tablename__ = "doctors"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve doctor record
    department_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("departments.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    specialty: Mapped[str] = mapped_column(
        String(100), nullable=False, index=True
    )  # cardiology, dermatology, stomatology
    cabinet: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    price_default: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    start_number_online: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    max_online_per_day: Mapped[int] = mapped_column(Integer, default=15, nullable=False)
    auto_close_time: Mapped[Optional[time]] = mapped_column(Time, default=time(9, 0), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[user_id])
    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="doctors")
    schedules: Mapped[List["Schedule"]] = relationship(
        "Schedule", back_populates="doctor", cascade="all, delete-orphan"
    )
    services: Mapped[List["Service"]] = relationship("Service", back_populates="doctor")
    visits: Mapped[List["Visit"]] = relationship("Visit", back_populates="doctor")
    price_overrides: Mapped[List["DoctorPriceOverride"]] = relationship(
        "DoctorPriceOverride", back_populates="doctor"
    )


class Schedule(Base):
    """Расписание врачей"""

    __tablename__ = "schedules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    doctor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("doctors.id", ondelete="CASCADE"), nullable=False
    )
    weekday: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    start_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    end_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    breaks: Mapped[Optional[List[Dict[str, str]]]] = mapped_column(
        JSON, nullable=True
    )  # [{"start": "12:00", "end": "13:00"}]
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    doctor: Mapped["Doctor"] = relationship("Doctor", back_populates="schedules")


class ServiceCategory(Base):
    """Категории услуг"""

    __tablename__ = "service_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name_ru: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name_uz: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    name_en: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    specialty: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, index=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    services: Mapped[List["Service"]] = relationship("Service", back_populates="category")


# ===================== ФИЛИАЛЫ КЛИНИКИ =====================


class BranchStatus(str, enum.Enum):
    """Статусы филиалов"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    CLOSED = "closed"


class Branch(Base):
    """Филиалы клиники"""

    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    manager_id: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve branch record
    status: Mapped[BranchStatus] = mapped_column(
        Enum(BranchStatus), default=BranchStatus.ACTIVE, nullable=False
    )
    timezone: Mapped[str] = mapped_column(String(50), default="Asia/Tashkent", nullable=False)
    working_hours: Mapped[Optional[Dict[str, Any]]] = mapped_column(
        JSON, nullable=True
    )  # {"monday": {"start": "08:00", "end": "18:00"}}
    services_available: Mapped[Optional[List[str]]] = mapped_column(
        JSON, nullable=True
    )  # ["cardiology", "dermatology"]
    capacity: Mapped[int] = mapped_column(Integer, default=50, nullable=False)  # Максимальная вместимость
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    manager: Mapped[Optional["User"]] = relationship("User", foreign_keys=[manager_id])
    doctors: Mapped[List["Doctor"]] = relationship("Doctor", back_populates="branch")
    equipment: Mapped[List["Equipment"]] = relationship("Equipment", back_populates="branch")


# ===================== ОБОРУДОВАНИЕ =====================


class EquipmentStatus(str, enum.Enum):
    """Статусы оборудования"""

    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    BROKEN = "broken"
    REPLACED = "replaced"


class EquipmentType(str, enum.Enum):
    """Типы оборудования"""

    MEDICAL = "medical"
    DIAGNOSTIC = "diagnostic"
    SURGICAL = "surgical"
    LABORATORY = "laboratory"
    OFFICE = "office"
    IT = "it"


class Equipment(Base):
    """Оборудование клиники"""

    __tablename__ = "equipment"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    serial_number: Mapped[Optional[str]] = mapped_column(
        String(100), unique=True, nullable=True, index=True
    )
    equipment_type: Mapped[EquipmentType] = mapped_column(Enum(EquipmentType), nullable=False)
    branch_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("branches.id", ondelete="CASCADE"), nullable=False
    )
    cabinet: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    status: Mapped[EquipmentStatus] = mapped_column(
        Enum(EquipmentStatus), default=EquipmentStatus.ACTIVE, nullable=False
    )
    purchase_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    warranty_expires: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_maintenance: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_maintenance: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    supplier: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    branch: Mapped["Branch"] = relationship("Branch", back_populates="equipment")
    maintenance_records: Mapped[List["EquipmentMaintenance"]] = relationship(
        "EquipmentMaintenance", back_populates="equipment", cascade="all, delete-orphan"
    )


class EquipmentMaintenance(Base):
    """Записи обслуживания оборудования"""

    __tablename__ = "equipment_maintenance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    equipment_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False
    )
    maintenance_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # preventive, repair, calibration
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    performed_by: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 2), nullable=True)
    maintenance_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    next_maintenance: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    equipment: Mapped["Equipment"] = relationship("Equipment", back_populates="maintenance_records")


# ===================== ЛИЦЕНЗИИ И АКТИВАЦИЯ =====================


class LicenseStatus(str, enum.Enum):
    """Статусы лицензий"""

    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    PENDING = "pending"


class LicenseType(str, enum.Enum):
    """Типы лицензий"""

    SOFTWARE = "software"
    MEDICAL = "medical"
    BUSINESS = "business"
    DATA = "data"


class License(Base):
    """Лицензии клиники"""

    __tablename__ = "licenses"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    license_type: Mapped[LicenseType] = mapped_column(Enum(LicenseType), nullable=False)
    license_key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus), default=LicenseStatus.ACTIVE, nullable=False
    )
    issued_by: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    issued_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    expires_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    renewal_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    cost: Mapped[Optional[Decimal]] = mapped_column(Numeric(12, 2), nullable=True)
    features: Mapped[Optional[List[str]]] = mapped_column(JSON, nullable=True)  # Список доступных функций
    restrictions: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)  # Ограничения лицензии
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    activations: Mapped[List["LicenseActivation"]] = relationship(
        "LicenseActivation", back_populates="license", cascade="all, delete-orphan"
    )


class LicenseActivation(Base):
    """Активации лицензий"""

    __tablename__ = "license_activations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    license_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False
    )
    activated_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    activation_date: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    machine_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)  # Уникальный ID машины
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    status: Mapped[LicenseStatus] = mapped_column(
        Enum(LicenseStatus), default=LicenseStatus.ACTIVE, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    license: Mapped["License"] = relationship("License", back_populates="activations")
    activated_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[activated_by])


# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================


class BackupStatus(str, enum.Enum):
    """Статусы резервного копирования"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class BackupType(str, enum.Enum):
    """Типы резервного копирования"""

    FULL = "full"
    INCREMENTAL = "incremental"
    DIFFERENTIAL = "differential"
    MANUAL = "manual"


class Backup(Base):
    """Резервные копии"""

    __tablename__ = "backups"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False, index=True)
    backup_type: Mapped[BackupType] = mapped_column(Enum(BackupType), nullable=False)
    status: Mapped[BackupStatus] = mapped_column(
        Enum(BackupStatus), default=BackupStatus.PENDING, nullable=False
    )
    file_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    file_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # Размер в байтах
    created_by: Mapped[Optional[int]] = mapped_column(
        Integer, 
        ForeignKey("users.id", ondelete="SET NULL"), 
        nullable=True
    )  # ✅ SECURITY: SET NULL to preserve audit trail
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    created_by_user: Mapped[Optional["User"]] = relationship("User", foreign_keys=[created_by])


# ===================== СИСТЕМНАЯ ИНФОРМАЦИЯ =====================


class SystemInfo(Base):
    """Системная информация"""

    __tablename__ = "system_info"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    key: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    value: Mapped[Optional[Any]] = mapped_column(JSON, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    updated_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    created_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


# ===================== ОБНОВЛЕНИЯ СВЯЗЕЙ =====================

# Обновляем модель Doctor для связи с филиалами
Doctor.branch_id = mapped_column(Integer, ForeignKey("branches.id"), nullable=True)
Doctor.branch = relationship("Branch", back_populates="doctors")

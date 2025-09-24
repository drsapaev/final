"""
Модели для управления клиникой в админ панели
"""
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, Time, Numeric, JSON, Date, Enum
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.db.base_class import Base
import enum


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
    visits = relationship("Visit", back_populates="doctor")
    price_overrides = relationship("DoctorPriceOverride", back_populates="doctor")


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
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False, index=True)
    code = Column(String(20), unique=True, nullable=False, index=True)
    address = Column(Text, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(100), nullable=True)
    manager_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    status = Column(Enum(BranchStatus), default=BranchStatus.ACTIVE, nullable=False)
    timezone = Column(String(50), default="Asia/Tashkent", nullable=False)
    working_hours = Column(JSON, nullable=True)  # {"monday": {"start": "08:00", "end": "18:00"}}
    services_available = Column(JSON, nullable=True)  # ["cardiology", "dermatology"]
    capacity = Column(Integer, default=50, nullable=False)  # Максимальная вместимость
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    manager = relationship("User", foreign_keys=[manager_id])
    doctors = relationship("Doctor", back_populates="branch")
    equipment = relationship("Equipment", back_populates="branch")


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
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    model = Column(String(100), nullable=True)
    serial_number = Column(String(100), unique=True, nullable=True, index=True)
    equipment_type = Column(Enum(EquipmentType), nullable=False)
    branch_id = Column(Integer, ForeignKey("branches.id"), nullable=False)
    cabinet = Column(String(20), nullable=True)
    status = Column(Enum(EquipmentStatus), default=EquipmentStatus.ACTIVE, nullable=False)
    purchase_date = Column(Date, nullable=True)
    warranty_expires = Column(Date, nullable=True)
    last_maintenance = Column(DateTime(timezone=True), nullable=True)
    next_maintenance = Column(DateTime(timezone=True), nullable=True)
    cost = Column(Numeric(12, 2), nullable=True)
    supplier = Column(String(200), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    branch = relationship("Branch", back_populates="equipment")
    maintenance_records = relationship("EquipmentMaintenance", back_populates="equipment", cascade="all, delete-orphan")


class EquipmentMaintenance(Base):
    """Записи обслуживания оборудования"""
    __tablename__ = "equipment_maintenance"
    
    id = Column(Integer, primary_key=True, index=True)
    equipment_id = Column(Integer, ForeignKey("equipment.id", ondelete="CASCADE"), nullable=False)
    maintenance_type = Column(String(50), nullable=False)  # preventive, repair, calibration
    description = Column(Text, nullable=True)
    performed_by = Column(String(100), nullable=True)
    cost = Column(Numeric(10, 2), nullable=True)
    maintenance_date = Column(DateTime(timezone=True), nullable=False)
    next_maintenance = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    equipment = relationship("Equipment", back_populates="maintenance_records")


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
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    license_type = Column(Enum(LicenseType), nullable=False)
    license_key = Column(String(255), unique=True, nullable=False, index=True)
    status = Column(Enum(LicenseStatus), default=LicenseStatus.ACTIVE, nullable=False)
    issued_by = Column(String(200), nullable=True)
    issued_date = Column(Date, nullable=True)
    expires_date = Column(Date, nullable=True)
    renewal_date = Column(Date, nullable=True)
    cost = Column(Numeric(12, 2), nullable=True)
    features = Column(JSON, nullable=True)  # Список доступных функций
    restrictions = Column(JSON, nullable=True)  # Ограничения лицензии
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    activations = relationship("LicenseActivation", back_populates="license", cascade="all, delete-orphan")


class LicenseActivation(Base):
    """Активации лицензий"""
    __tablename__ = "license_activations"
    
    id = Column(Integer, primary_key=True, index=True)
    license_id = Column(Integer, ForeignKey("licenses.id", ondelete="CASCADE"), nullable=False)
    activated_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    activation_date = Column(DateTime(timezone=True), server_default=func.now())
    machine_id = Column(String(100), nullable=True)  # Уникальный ID машины
    ip_address = Column(String(45), nullable=True)
    status = Column(Enum(LicenseStatus), default=LicenseStatus.ACTIVE, nullable=False)
    notes = Column(Text, nullable=True)
    
    # Relationships
    license = relationship("License", back_populates="activations")
    activated_by_user = relationship("User", foreign_keys=[activated_by])


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
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    backup_type = Column(Enum(BackupType), nullable=False)
    status = Column(Enum(BackupStatus), default=BackupStatus.PENDING, nullable=False)
    file_path = Column(String(500), nullable=True)
    file_size = Column(Integer, nullable=True)  # Размер в байтах
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error_message = Column(Text, nullable=True)
    retention_days = Column(Integer, default=30, nullable=False)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    created_by_user = relationship("User", foreign_keys=[created_by])


# ===================== СИСТЕМНАЯ ИНФОРМАЦИЯ =====================

class SystemInfo(Base):
    """Системная информация"""
    __tablename__ = "system_info"
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, nullable=False, index=True)
    value = Column(JSON, nullable=True)
    description = Column(Text, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ===================== ОБНОВЛЕНИЯ СВЯЗЕЙ =====================

# Обновляем модель Doctor для связи с филиалами
Doctor.branch_id = Column(Integer, ForeignKey("branches.id"), nullable=True)
Doctor.branch = relationship("Branch", back_populates="doctors")

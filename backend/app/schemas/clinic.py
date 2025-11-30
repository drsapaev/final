"""
Pydantic схемы для управления клиникой в админ панели
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

# ===================== НАСТРОЙКИ КЛИНИКИ =====================


class ClinicSettingsBase(BaseModel):
    key: str = Field(..., max_length=100)
    value: Optional[Dict[str, Any]] = None
    category: Optional[str] = Field(None, max_length=50)
    description: Optional[str] = None


class ClinicSettingsCreate(ClinicSettingsBase):
    pass


class ClinicSettingsUpdate(BaseModel):
    value: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class ClinicSettingsOut(ClinicSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class ClinicSettingsBatch(BaseModel):
    """Массовое обновление настроек"""

    settings: Dict[str, Any] = Field(..., description="Словарь настроек {key: value}")


# ===================== ВРАЧИ =====================


class DoctorBase(BaseModel):
    user_id: Optional[int] = None
    specialty: str = Field(
        ..., max_length=100, description="cardiology, dermatology, stomatology"
    )
    cabinet: Optional[str] = Field(None, max_length=20)
    price_default: Optional[Decimal] = Field(None, ge=0)
    start_number_online: int = Field(1, ge=1, le=100)
    max_online_per_day: int = Field(15, ge=1, le=100)
    auto_close_time: Optional[time] = Field(
        None, description="Время автозакрытия очереди"
    )
    active: bool = True


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(BaseModel):
    user_id: Optional[int] = None
    specialty: Optional[str] = Field(None, max_length=100)
    cabinet: Optional[str] = Field(None, max_length=20)
    price_default: Optional[Decimal] = Field(None, ge=0)
    start_number_online: Optional[int] = Field(None, ge=1, le=100)
    max_online_per_day: Optional[int] = Field(None, ge=1, le=100)
    auto_close_time: Optional[time] = None
    active: Optional[bool] = None


class DoctorOut(DoctorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Связанные данные
    user: Optional[Dict[str, Any]] = None
    schedules: List["ScheduleOut"] = []


# ===================== РАСПИСАНИЯ =====================


class ScheduleBase(BaseModel):
    weekday: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    breaks: Optional[List[Dict[str, str]]] = Field(
        None, description='[{"start": "12:00", "end": "13:00"}]'
    )
    active: bool = True


class ScheduleCreate(ScheduleBase):
    doctor_id: int


class ScheduleUpdate(BaseModel):
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    breaks: Optional[List[Dict[str, str]]] = None
    active: Optional[bool] = None


class ScheduleOut(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    created_at: Optional[datetime] = None


class WeeklyScheduleUpdate(BaseModel):
    """Обновление расписания на всю неделю"""

    schedules: List[ScheduleBase] = Field(..., max_items=7)


# ===================== КАТЕГОРИИ УСЛУГ =====================


class ServiceCategoryBase(BaseModel):
    code: str = Field(
        ...,
        max_length=50,
        description="consultation.cardiology, procedure.cosmetology, etc.",
    )
    name_ru: Optional[str] = Field(None, max_length=100)
    name_uz: Optional[str] = Field(None, max_length=100)
    name_en: Optional[str] = Field(None, max_length=100)
    specialty: Optional[str] = Field(
        None, max_length=100, description="cardiology, dermatology, stomatology"
    )
    active: bool = True


class ServiceCategoryCreate(ServiceCategoryBase):
    pass


class ServiceCategoryUpdate(BaseModel):
    name_ru: Optional[str] = Field(None, max_length=100)
    name_uz: Optional[str] = Field(None, max_length=100)
    name_en: Optional[str] = Field(None, max_length=100)
    specialty: Optional[str] = Field(None, max_length=100)
    active: Optional[bool] = None


class ServiceCategoryOut(ServiceCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None


# ===================== НАСТРОЙКИ ОЧЕРЕДЕЙ =====================


class QueueSettingsUpdate(BaseModel):
    """Настройки системы очередей"""

    timezone: str = Field("Asia/Tashkent", description="Часовой пояс")
    queue_start_hour: int = Field(
        7, ge=0, le=23, description="Час начала онлайн очереди"
    )
    auto_close_time: str = Field("09:00", description="Время автозакрытия")

    # Настройки по специальностям
    start_numbers: Dict[str, int] = Field(
        default={"cardiology": 1, "dermatology": 15, "stomatology": 3},
        description="Стартовые номера по специальностям",
    )

    max_per_day: Dict[str, int] = Field(
        default={"cardiology": 15, "dermatology": 20, "stomatology": 12},
        description="Максимум онлайн записей в день",
    )


class QueueTestRequest(BaseModel):
    """Запрос на тестирование очереди"""

    doctor_id: int
    date: Optional[str] = None  # YYYY-MM-DD format


# ===================== ФИЛИАЛЫ КЛИНИКИ =====================


class BranchBase(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=20)
    address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    manager_id: Optional[int] = None
    status: str = Field("active", description="active, inactive, maintenance, closed")
    timezone: str = Field("Asia/Tashkent", max_length=50)
    working_hours: Optional[Dict[str, Dict[str, str]]] = Field(
        None, description='{"monday": {"start": "08:00", "end": "18:00"}}'
    )
    services_available: Optional[List[str]] = Field(
        None, description='["cardiology", "dermatology"]'
    )
    capacity: int = Field(50, ge=1, le=1000)


class BranchCreate(BranchBase):
    pass


class BranchUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=100)
    address: Optional[str] = None
    phone: Optional[str] = Field(None, max_length=20)
    email: Optional[str] = Field(None, max_length=100)
    manager_id: Optional[int] = None
    status: Optional[str] = Field(
        None, description="active, inactive, maintenance, closed"
    )
    timezone: Optional[str] = Field(None, max_length=50)
    working_hours: Optional[Dict[str, Dict[str, str]]] = None
    services_available: Optional[List[str]] = None
    capacity: Optional[int] = Field(None, ge=1, le=1000)


class BranchOut(BranchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Связанные данные
    manager: Optional[Dict[str, Any]] = None
    doctors_count: Optional[int] = 0
    equipment_count: Optional[int] = 0

    @classmethod
    def from_orm(cls, obj):
        """Переопределяем from_orm для правильной обработки связанных данных"""
        data = obj.__dict__.copy()

        # Преобразуем связанные объекты в словари
        if hasattr(obj, 'manager') and obj.manager:
            data['manager'] = {
                'id': obj.manager.id,
                'username': obj.manager.username,
                'full_name': obj.manager.full_name,
                'email': obj.manager.email,
            }

        # Подсчитываем количество врачей и оборудования
        if hasattr(obj, 'doctors'):
            data['doctors_count'] = len(obj.doctors) if obj.doctors else 0
        if hasattr(obj, 'equipment'):
            data['equipment_count'] = len(obj.equipment) if obj.equipment else 0

        return cls(**data)


# ===================== ОБОРУДОВАНИЕ =====================


class EquipmentBase(BaseModel):
    name: str = Field(..., max_length=200)
    model: Optional[str] = Field(None, max_length=100)
    serial_number: Optional[str] = Field(None, max_length=100)
    equipment_type: str = Field(
        ..., description="medical, diagnostic, surgical, laboratory, office, it"
    )
    branch_id: int
    cabinet: Optional[str] = Field(None, max_length=20)
    status: str = Field(
        "active", description="active, inactive, maintenance, broken, replaced"
    )
    purchase_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    warranty_expires: Optional[str] = Field(None, description="YYYY-MM-DD")
    cost: Optional[Decimal] = Field(None, ge=0)
    supplier: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    model: Optional[str] = Field(None, max_length=100)
    serial_number: Optional[str] = Field(None, max_length=100)
    equipment_type: Optional[str] = Field(
        None, description="medical, diagnostic, surgical, laboratory, office, it"
    )
    branch_id: Optional[int] = None
    cabinet: Optional[str] = Field(None, max_length=20)
    status: Optional[str] = Field(
        None, description="active, inactive, maintenance, broken, replaced"
    )
    purchase_date: Optional[str] = Field(None, description="YYYY-MM-DD")
    warranty_expires: Optional[str] = Field(None, description="YYYY-MM-DD")
    cost: Optional[Decimal] = Field(None, ge=0)
    supplier: Optional[str] = Field(None, max_length=200)
    notes: Optional[str] = None


class EquipmentOut(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_maintenance: Optional[datetime] = None
    next_maintenance: Optional[datetime] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Связанные данные
    branch: Optional[Dict[str, Any]] = None
    maintenance_records_count: Optional[int] = 0

    @classmethod
    def from_orm(cls, obj):
        """Переопределяем from_orm для правильной обработки связанных данных"""
        data = obj.__dict__.copy()

        # Преобразуем связанные объекты в словари
        if hasattr(obj, 'branch') and obj.branch:
            data['branch'] = {
                'id': obj.branch.id,
                'name': obj.branch.name,
                'code': obj.branch.code,
                'status': (
                    obj.branch.status.value
                    if hasattr(obj.branch.status, 'value')
                    else str(obj.branch.status)
                ),
            }

        # Подсчитываем количество записей обслуживания
        if hasattr(obj, 'maintenance_records'):
            data['maintenance_records_count'] = (
                len(obj.maintenance_records) if obj.maintenance_records else 0
            )

        return cls(**data)


class EquipmentMaintenanceBase(BaseModel):
    maintenance_type: str = Field(..., description="preventive, repair, calibration")
    description: Optional[str] = None
    performed_by: Optional[str] = Field(None, max_length=100)
    cost: Optional[Decimal] = Field(None, ge=0)
    maintenance_date: datetime
    next_maintenance: Optional[datetime] = None
    notes: Optional[str] = None


class EquipmentMaintenanceCreate(EquipmentMaintenanceBase):
    equipment_id: int


class EquipmentMaintenanceUpdate(BaseModel):
    maintenance_type: Optional[str] = Field(
        None, description="preventive, repair, calibration"
    )
    description: Optional[str] = None
    performed_by: Optional[str] = Field(None, max_length=100)
    cost: Optional[Decimal] = Field(None, ge=0)
    maintenance_date: Optional[datetime] = None
    next_maintenance: Optional[datetime] = None
    notes: Optional[str] = None


class EquipmentMaintenanceOut(EquipmentMaintenanceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    created_at: Optional[datetime] = None


# ===================== ЛИЦЕНЗИИ =====================


class LicenseBase(BaseModel):
    name: str = Field(..., max_length=200)
    license_type: str = Field(..., description="software, medical, business, data")
    license_key: str = Field(..., max_length=255)
    status: str = Field("active", description="active, expired, suspended, pending")
    issued_by: Optional[str] = Field(None, max_length=200)
    issued_date: Optional[date] = Field(None, description="Дата выдачи")
    expires_date: Optional[date] = Field(None, description="Дата истечения")
    renewal_date: Optional[date] = Field(None, description="Дата продления")
    cost: Optional[Decimal] = Field(None, ge=0)
    features: Optional[List[str]] = Field(None, description="Список доступных функций")
    restrictions: Optional[List[str]] = Field(None, description="Ограничения лицензии")
    notes: Optional[str] = None


class LicenseCreate(LicenseBase):
    pass


class LicenseUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    license_type: Optional[str] = Field(
        None, description="software, medical, business, data"
    )
    status: Optional[str] = Field(
        None, description="active, expired, suspended, pending"
    )
    issued_by: Optional[str] = Field(None, max_length=200)
    issued_date: Optional[date] = Field(None, description="Дата выдачи")
    expires_date: Optional[date] = Field(None, description="Дата истечения")
    renewal_date: Optional[date] = Field(None, description="Дата продления")
    cost: Optional[Decimal] = Field(None, ge=0)
    features: Optional[List[str]] = None
    restrictions: Optional[List[str]] = None
    notes: Optional[str] = None


class LicenseOut(LicenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    # Связанные данные
    activations_count: Optional[int] = 0


class LicenseActivationBase(BaseModel):
    machine_id: Optional[str] = Field(None, max_length=100)
    ip_address: Optional[str] = Field(None, max_length=45)
    status: str = Field("active", description="active, expired, suspended, pending")
    notes: Optional[str] = None


class LicenseActivationCreate(LicenseActivationBase):
    license_id: int


class LicenseActivationUpdate(BaseModel):
    machine_id: Optional[str] = Field(None, max_length=100)
    ip_address: Optional[str] = Field(None, max_length=45)
    status: Optional[str] = Field(
        None, description="active, expired, suspended, pending"
    )
    notes: Optional[str] = None


class LicenseActivationOut(LicenseActivationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    license_id: int
    activated_by: Optional[int] = None
    activation_date: Optional[datetime] = None


# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================


class BackupBase(BaseModel):
    name: str = Field(..., max_length=200)
    backup_type: str = Field(..., description="full, incremental, differential, manual")
    status: str = Field(
        "pending", description="pending, in_progress, completed, failed, cancelled"
    )
    file_path: Optional[str] = Field(None, max_length=500)
    file_size: Optional[int] = Field(None, ge=0)
    retention_days: int = Field(30, ge=1, le=365)
    notes: Optional[str] = None


class BackupCreate(BackupBase):
    pass


class BackupUpdate(BaseModel):
    name: Optional[str] = Field(None, max_length=200)
    backup_type: Optional[str] = Field(
        None, description="full, incremental, differential, manual"
    )
    status: Optional[str] = Field(
        None, description="pending, in_progress, completed, failed, cancelled"
    )
    retention_days: Optional[int] = Field(None, ge=1, le=365)
    notes: Optional[str] = None


class BackupOut(BackupBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: Optional[int] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    expires_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ===================== СИСТЕМНАЯ ИНФОРМАЦИЯ =====================


class SystemInfoBase(BaseModel):
    key: str = Field(..., max_length=100)
    value: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class SystemInfoCreate(SystemInfoBase):
    pass


class SystemInfoUpdate(BaseModel):
    value: Optional[Dict[str, Any]] = None
    description: Optional[str] = None


class SystemInfoOut(SystemInfoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


# ===================== СТАТИСТИКА И ОТЧЕТЫ =====================


class ClinicStatsOut(BaseModel):
    """Статистика клиники"""

    total_branches: int
    active_branches: int
    total_doctors: int
    active_doctors: int
    total_equipment: int
    active_equipment: int
    equipment_in_maintenance: int
    total_licenses: int
    active_licenses: int
    expired_licenses: int
    total_backups: int
    recent_backups: int
    system_health: str  # healthy, warning, critical


class BranchStatsOut(BaseModel):
    """Статистика филиала"""

    branch_id: int
    branch_name: str
    doctors_count: int
    equipment_count: int
    active_equipment: int
    maintenance_due: int
    last_backup: Optional[datetime] = None
    status: str

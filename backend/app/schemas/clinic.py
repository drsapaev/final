"""
Pydantic схемы для управления клиникой в админ панели
"""

from datetime import date, datetime, time
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ===================== НАСТРОЙКИ КЛИНИКИ =====================


class ClinicSettingsBase(BaseModel):
    key: str = Field(..., max_length=100)
    value: Any | None = None  # Can be any JSON-serializable value (string, dict, list, etc.)
    category: str | None = Field(None, max_length=50)
    description: str | None = None


class ClinicSettingsCreate(ClinicSettingsBase):
    pass


class ClinicSettingsUpdate(BaseModel):
    value: Any | None = None  # Can be any JSON-serializable value
    description: str | None = None


class ClinicSettingsOut(ClinicSettingsBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_by: int | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class ClinicSettingsBatch(BaseModel):
    """Массовое обновление настроек"""

    settings: dict[str, Any] = Field(..., description="Словарь настроек {key: value}")


# ===================== ВРАЧИ =====================


class DoctorBase(BaseModel):
    user_id: int | None = None
    specialty: str = Field(
        ..., max_length=100, description="cardiology, dermatology, stomatology"
    )
    cabinet: str | None = Field(None, max_length=20)
    price_default: Decimal | None = Field(None, ge=0)
    start_number_online: int = Field(1, ge=1, le=100)
    max_online_per_day: int = Field(15, ge=1, le=100)
    auto_close_time: time | None = Field(
        None, description="Время автозакрытия очереди"
    )
    active: bool = True


class DoctorCreate(DoctorBase):
    pass


class DoctorUpdate(BaseModel):
    user_id: int | None = None
    specialty: str | None = Field(None, max_length=100)
    cabinet: str | None = Field(None, max_length=20)
    price_default: Decimal | None = Field(None, ge=0)
    start_number_online: int | None = Field(None, ge=1, le=100)
    max_online_per_day: int | None = Field(None, ge=1, le=100)
    auto_close_time: time | None = None
    active: bool | None = None


class DoctorOut(DoctorBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Связанные данные
    user: dict[str, Any] | None = None
    schedules: list["ScheduleOut"] = []


# ===================== РАСПИСАНИЯ =====================


class ScheduleBase(BaseModel):
    weekday: int = Field(..., ge=0, le=6, description="0=Monday, 6=Sunday")
    start_time: time | None = None
    end_time: time | None = None
    breaks: list[dict[str, str]] | None = Field(
        None, description='[{"start": "12:00", "end": "13:00"}]'
    )
    active: bool = True


class ScheduleCreate(ScheduleBase):
    doctor_id: int


class ScheduleUpdate(BaseModel):
    start_time: time | None = None
    end_time: time | None = None
    breaks: list[dict[str, str]] | None = None
    active: bool | None = None


class ScheduleOut(ScheduleBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    doctor_id: int
    created_at: datetime | None = None


class WeeklyScheduleUpdate(BaseModel):
    """Обновление расписания на всю неделю"""

    schedules: list[ScheduleBase] = Field(..., max_items=7)


# ===================== КАТЕГОРИИ УСЛУГ =====================


class ServiceCategoryBase(BaseModel):
    code: str = Field(
        ...,
        max_length=50,
        description="consultation.cardiology, procedure.cosmetology, etc.",
    )
    name_ru: str | None = Field(None, max_length=100)
    name_uz: str | None = Field(None, max_length=100)
    name_en: str | None = Field(None, max_length=100)
    specialty: str | None = Field(
        None, max_length=100, description="cardiology, dermatology, stomatology"
    )
    active: bool = True


class ServiceCategoryCreate(ServiceCategoryBase):
    pass


class ServiceCategoryUpdate(BaseModel):
    name_ru: str | None = Field(None, max_length=100)
    name_uz: str | None = Field(None, max_length=100)
    name_en: str | None = Field(None, max_length=100)
    specialty: str | None = Field(None, max_length=100)
    active: bool | None = None


class ServiceCategoryOut(ServiceCategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None


# ===================== НАСТРОЙКИ ОЧЕРЕДЕЙ =====================


class QueueSettingsUpdate(BaseModel):
    """Настройки системы очередей"""

    timezone: str = Field("Asia/Tashkent", description="Часовой пояс")
    queue_start_hour: int = Field(
        7, ge=0, le=23, description="Час начала онлайн очереди"
    )
    auto_close_time: str = Field("09:00", description="Время автозакрытия")

    # Настройки по специальностям
    start_numbers: dict[str, int] = Field(
        default={"cardiology": 1, "dermatology": 15, "stomatology": 3},
        description="Стартовые номера по специальностям",
    )

    max_per_day: dict[str, int] = Field(
        default={"cardiology": 15, "dermatology": 20, "stomatology": 12},
        description="Максимум онлайн записей в день",
    )


class QueueTestRequest(BaseModel):
    """Запрос на тестирование очереди"""

    doctor_id: int
    date: str | None = None  # YYYY-MM-DD format


# ===================== ФИЛИАЛЫ КЛИНИКИ =====================


class BranchBase(BaseModel):
    name: str = Field(..., max_length=100)
    code: str = Field(..., max_length=20)
    address: str | None = None
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    manager_id: int | None = None
    status: str = Field("active", description="active, inactive, maintenance, closed")
    timezone: str = Field("Asia/Tashkent", max_length=50)
    working_hours: dict[str, dict[str, str]] | None = Field(
        None, description='{"monday": {"start": "08:00", "end": "18:00"}}'
    )
    services_available: list[str] | None = Field(
        None, description='["cardiology", "dermatology"]'
    )
    capacity: int = Field(50, ge=1, le=1000)


class BranchCreate(BranchBase):
    pass


class BranchUpdate(BaseModel):
    name: str | None = Field(None, max_length=100)
    address: str | None = None
    phone: str | None = Field(None, max_length=20)
    email: str | None = Field(None, max_length=100)
    manager_id: int | None = None
    status: str | None = Field(
        None, description="active, inactive, maintenance, closed"
    )
    timezone: str | None = Field(None, max_length=50)
    working_hours: dict[str, dict[str, str]] | None = None
    services_available: list[str] | None = None
    capacity: int | None = Field(None, ge=1, le=1000)


class BranchOut(BranchBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Связанные данные
    manager: dict[str, Any] | None = None
    doctors_count: int | None = 0
    equipment_count: int | None = 0

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
    model: str | None = Field(None, max_length=100)
    serial_number: str | None = Field(None, max_length=100)
    equipment_type: str = Field(
        ..., description="medical, diagnostic, surgical, laboratory, office, it"
    )
    branch_id: int
    cabinet: str | None = Field(None, max_length=20)
    status: str = Field(
        "active", description="active, inactive, maintenance, broken, replaced"
    )
    purchase_date: str | None = Field(None, description="YYYY-MM-DD")
    warranty_expires: str | None = Field(None, description="YYYY-MM-DD")
    cost: Decimal | None = Field(None, ge=0)
    supplier: str | None = Field(None, max_length=200)
    notes: str | None = None


class EquipmentCreate(EquipmentBase):
    pass


class EquipmentUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    model: str | None = Field(None, max_length=100)
    serial_number: str | None = Field(None, max_length=100)
    equipment_type: str | None = Field(
        None, description="medical, diagnostic, surgical, laboratory, office, it"
    )
    branch_id: int | None = None
    cabinet: str | None = Field(None, max_length=20)
    status: str | None = Field(
        None, description="active, inactive, maintenance, broken, replaced"
    )
    purchase_date: str | None = Field(None, description="YYYY-MM-DD")
    warranty_expires: str | None = Field(None, description="YYYY-MM-DD")
    cost: Decimal | None = Field(None, ge=0)
    supplier: str | None = Field(None, max_length=200)
    notes: str | None = None


class EquipmentOut(EquipmentBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_maintenance: datetime | None = None
    next_maintenance: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Связанные данные
    branch: dict[str, Any] | None = None
    maintenance_records_count: int | None = 0

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
    description: str | None = None
    performed_by: str | None = Field(None, max_length=100)
    cost: Decimal | None = Field(None, ge=0)
    maintenance_date: datetime
    next_maintenance: datetime | None = None
    notes: str | None = None


class EquipmentMaintenanceCreate(EquipmentMaintenanceBase):
    equipment_id: int


class EquipmentMaintenanceUpdate(BaseModel):
    maintenance_type: str | None = Field(
        None, description="preventive, repair, calibration"
    )
    description: str | None = None
    performed_by: str | None = Field(None, max_length=100)
    cost: Decimal | None = Field(None, ge=0)
    maintenance_date: datetime | None = None
    next_maintenance: datetime | None = None
    notes: str | None = None


class EquipmentMaintenanceOut(EquipmentMaintenanceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    equipment_id: int
    created_at: datetime | None = None


# ===================== ЛИЦЕНЗИИ =====================


class LicenseBase(BaseModel):
    name: str = Field(..., max_length=200)
    license_type: str = Field(..., description="software, medical, business, data")
    license_key: str = Field(..., max_length=255)
    status: str = Field("active", description="active, expired, suspended, pending")
    issued_by: str | None = Field(None, max_length=200)
    issued_date: date | None = Field(None, description="Дата выдачи")
    expires_date: date | None = Field(None, description="Дата истечения")
    renewal_date: date | None = Field(None, description="Дата продления")
    cost: Decimal | None = Field(None, ge=0)
    features: list[str] | None = Field(None, description="Список доступных функций")
    restrictions: list[str] | None = Field(None, description="Ограничения лицензии")
    notes: str | None = None


class LicenseCreate(LicenseBase):
    pass


class LicenseUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    license_type: str | None = Field(
        None, description="software, medical, business, data"
    )
    status: str | None = Field(
        None, description="active, expired, suspended, pending"
    )
    issued_by: str | None = Field(None, max_length=200)
    issued_date: date | None = Field(None, description="Дата выдачи")
    expires_date: date | None = Field(None, description="Дата истечения")
    renewal_date: date | None = Field(None, description="Дата продления")
    cost: Decimal | None = Field(None, ge=0)
    features: list[str] | None = None
    restrictions: list[str] | None = None
    notes: str | None = None


class LicenseOut(LicenseBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # Связанные данные
    activations_count: int | None = 0


class LicenseActivationBase(BaseModel):
    machine_id: str | None = Field(None, max_length=100)
    ip_address: str | None = Field(None, max_length=45)
    status: str = Field("active", description="active, expired, suspended, pending")
    notes: str | None = None


class LicenseActivationCreate(LicenseActivationBase):
    license_id: int


class LicenseActivationUpdate(BaseModel):
    machine_id: str | None = Field(None, max_length=100)
    ip_address: str | None = Field(None, max_length=45)
    status: str | None = Field(
        None, description="active, expired, suspended, pending"
    )
    notes: str | None = None


class LicenseActivationOut(LicenseActivationBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    license_id: int
    activated_by: int | None = None
    activation_date: datetime | None = None


# ===================== РЕЗЕРВНОЕ КОПИРОВАНИЕ =====================


class BackupBase(BaseModel):
    name: str = Field(..., max_length=200)
    backup_type: str = Field(..., description="full, incremental, differential, manual")
    status: str = Field(
        "pending", description="pending, in_progress, completed, failed, cancelled"
    )
    file_path: str | None = Field(None, max_length=500)
    file_size: int | None = Field(None, ge=0)
    retention_days: int = Field(30, ge=1, le=365)
    notes: str | None = None


class BackupCreate(BackupBase):
    pass


class BackupUpdate(BaseModel):
    name: str | None = Field(None, max_length=200)
    backup_type: str | None = Field(
        None, description="full, incremental, differential, manual"
    )
    status: str | None = Field(
        None, description="pending, in_progress, completed, failed, cancelled"
    )
    retention_days: int | None = Field(None, ge=1, le=365)
    notes: str | None = None


class BackupOut(BackupBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_by: int | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error_message: str | None = None
    expires_at: datetime | None = None
    created_at: datetime | None = None


# ===================== СИСТЕМНАЯ ИНФОРМАЦИЯ =====================


class SystemInfoBase(BaseModel):
    key: str = Field(..., max_length=100)
    value: dict[str, Any] | None = None
    description: str | None = None


class SystemInfoCreate(SystemInfoBase):
    pass


class SystemInfoUpdate(BaseModel):
    value: dict[str, Any] | None = None
    description: str | None = None


class SystemInfoOut(SystemInfoBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    updated_at: datetime | None = None
    created_at: datetime | None = None


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
    last_backup: datetime | None = None
    status: str

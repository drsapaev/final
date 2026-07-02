"""
Pydantic схемы для Department API
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# DEPARTMENT SERVICE SCHEMAS
# ============================================================


class DepartmentServiceCreate(BaseModel):
    """Создание привязки услуги к отделению"""

    is_default: bool = False
    display_order: int = 999
    price_override: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentServiceUpdate(BaseModel):
    """Обновление привязки услуги к отделению"""

    is_default: bool | None = None
    display_order: int | None = None
    price_override: Decimal | None = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentServiceResponse(BaseModel):
    """Ответ с информацией о привязке услуги"""

    id: int
    department_id: int
    service_id: int
    is_default: bool
    display_order: int
    price_override: Decimal | None

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# DEPARTMENT QUEUE SETTINGS SCHEMAS
# ============================================================


class DepartmentQueueSettingsUpdate(BaseModel):
    """Обновление настроек очереди отделения"""

    enabled: bool | None = None
    queue_type: str | None = Field(None, pattern="^(live|online|mixed)$")
    queue_prefix: str | None = Field(None, max_length=10)
    max_daily_queue: int | None = Field(None, ge=1, le=200)
    max_concurrent_queue: int | None = Field(None, ge=1, le=50)
    avg_wait_time: int | None = Field(None, ge=1, le=120)
    show_on_display: bool | None = None
    auto_close_time: str | None = Field(
        None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$"
    )

    model_config = ConfigDict(from_attributes=True)


class DepartmentQueueSettingsResponse(BaseModel):
    """Ответ с настройками очереди"""

    id: int
    department_id: int
    enabled: bool
    queue_type: str
    queue_prefix: str | None
    max_daily_queue: int
    max_concurrent_queue: int
    avg_wait_time: int
    show_on_display: bool
    auto_close_time: str

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# DEPARTMENT REGISTRATION SETTINGS SCHEMAS
# ============================================================


class DepartmentRegistrationSettingsUpdate(BaseModel):
    """Обновление настроек регистрации отделения"""

    online_booking_enabled: bool | None = None
    requires_confirmation: bool | None = None
    min_booking_hours: int | None = Field(None, ge=0, le=168)  # Max 1 week
    max_booking_days: int | None = Field(None, ge=1, le=365)  # Max 1 year
    auto_assign_doctor: bool | None = None
    allow_walkin: bool | None = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentRegistrationSettingsResponse(BaseModel):
    """Ответ с настройками регистрации"""

    id: int
    department_id: int
    online_booking_enabled: bool
    requires_confirmation: bool
    min_booking_hours: int
    max_booking_days: int
    auto_assign_doctor: bool
    allow_walkin: bool

    model_config = ConfigDict(from_attributes=True)


# ============================================================
# DEPARTMENT BASE SCHEMAS
# ============================================================


class DepartmentBase(BaseModel):
    """Базовая схема отделения"""

    key: str = Field(..., max_length=50)
    name_ru: str = Field(..., max_length=200)
    name_uz: str | None = Field(None, max_length=200)
    icon: str | None = Field("folder", max_length=50)
    color: str | None = Field(None, max_length=50)
    gradient: str | None = None
    display_order: int = 999
    active: bool = True
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentCreate(DepartmentBase):
    """Создание отделения"""

    pass


class DepartmentUpdate(BaseModel):
    """Обновление отделения"""

    key: str | None = Field(None, max_length=50)
    name_ru: str | None = Field(None, max_length=200)
    name_uz: str | None = Field(None, max_length=200)
    icon: str | None = Field(None, max_length=50)
    color: str | None = Field(None, max_length=50)
    gradient: str | None = None
    display_order: int | None = None
    active: bool | None = None
    description: str | None = None

    model_config = ConfigDict(from_attributes=True)


class DepartmentResponse(DepartmentBase):
    """Ответ с информацией об отделении"""

    id: int

    model_config = ConfigDict(from_attributes=True)


class DepartmentFullResponse(DepartmentResponse):
    """Полный ответ с настройками и статистикой"""

    services_count: int | None = 0
    doctors_count: int | None = 0
    has_queue_settings: bool = False
    has_registration_settings: bool = False

    model_config = ConfigDict(from_attributes=True)

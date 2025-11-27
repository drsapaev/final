"""
Pydantic схемы для Department API
"""
from __future__ import annotations

from decimal import Decimal
from typing import Optional
from pydantic import BaseModel, Field


# ============================================================
# DEPARTMENT SERVICE SCHEMAS
# ============================================================

class DepartmentServiceCreate(BaseModel):
    """Создание привязки услуги к отделению"""
    is_default: bool = False
    display_order: int = 999
    price_override: Optional[Decimal] = None

    class Config:
        from_attributes = True


class DepartmentServiceUpdate(BaseModel):
    """Обновление привязки услуги к отделению"""
    is_default: Optional[bool] = None
    display_order: Optional[int] = None
    price_override: Optional[Decimal] = None

    class Config:
        from_attributes = True


class DepartmentServiceResponse(BaseModel):
    """Ответ с информацией о привязке услуги"""
    id: int
    department_id: int
    service_id: int
    is_default: bool
    display_order: int
    price_override: Optional[Decimal]

    class Config:
        from_attributes = True


# ============================================================
# DEPARTMENT QUEUE SETTINGS SCHEMAS
# ============================================================

class DepartmentQueueSettingsUpdate(BaseModel):
    """Обновление настроек очереди отделения"""
    enabled: Optional[bool] = None
    queue_type: Optional[str] = Field(None, pattern="^(live|online|mixed)$")
    queue_prefix: Optional[str] = Field(None, max_length=10)
    max_daily_queue: Optional[int] = Field(None, ge=1, le=200)
    max_concurrent_queue: Optional[int] = Field(None, ge=1, le=50)
    avg_wait_time: Optional[int] = Field(None, ge=1, le=120)
    show_on_display: Optional[bool] = None
    auto_close_time: Optional[str] = Field(None, pattern="^([01]?[0-9]|2[0-3]):[0-5][0-9]$")

    class Config:
        from_attributes = True


class DepartmentQueueSettingsResponse(BaseModel):
    """Ответ с настройками очереди"""
    id: int
    department_id: int
    enabled: bool
    queue_type: str
    queue_prefix: Optional[str]
    max_daily_queue: int
    max_concurrent_queue: int
    avg_wait_time: int
    show_on_display: bool
    auto_close_time: str

    class Config:
        from_attributes = True


# ============================================================
# DEPARTMENT REGISTRATION SETTINGS SCHEMAS
# ============================================================

class DepartmentRegistrationSettingsUpdate(BaseModel):
    """Обновление настроек регистрации отделения"""
    online_booking_enabled: Optional[bool] = None
    requires_confirmation: Optional[bool] = None
    min_booking_hours: Optional[int] = Field(None, ge=0, le=168)  # Max 1 week
    max_booking_days: Optional[int] = Field(None, ge=1, le=365)  # Max 1 year
    auto_assign_doctor: Optional[bool] = None
    allow_walkin: Optional[bool] = None

    class Config:
        from_attributes = True


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

    class Config:
        from_attributes = True


# ============================================================
# DEPARTMENT BASE SCHEMAS
# ============================================================

class DepartmentBase(BaseModel):
    """Базовая схема отделения"""
    key: str = Field(..., max_length=50)
    name_ru: str = Field(..., max_length=200)
    name_uz: Optional[str] = Field(None, max_length=200)
    icon: Optional[str] = Field("folder", max_length=50)
    color: Optional[str] = Field(None, max_length=50)
    gradient: Optional[str] = None
    display_order: int = 999
    active: bool = True
    description: Optional[str] = None

    class Config:
        from_attributes = True


class DepartmentCreate(DepartmentBase):
    """Создание отделения"""
    pass


class DepartmentUpdate(BaseModel):
    """Обновление отделения"""
    key: Optional[str] = Field(None, max_length=50)
    name_ru: Optional[str] = Field(None, max_length=200)
    name_uz: Optional[str] = Field(None, max_length=200)
    icon: Optional[str] = Field(None, max_length=50)
    color: Optional[str] = Field(None, max_length=50)
    gradient: Optional[str] = None
    display_order: Optional[int] = None
    active: Optional[bool] = None
    description: Optional[str] = None

    class Config:
        from_attributes = True


class DepartmentResponse(DepartmentBase):
    """Ответ с информацией об отделении"""
    id: int

    class Config:
        from_attributes = True


class DepartmentFullResponse(DepartmentResponse):
    """Полный ответ с настройками и статистикой"""
    services_count: Optional[int] = 0
    doctors_count: Optional[int] = 0
    has_queue_settings: bool = False
    has_registration_settings: bool = False

    class Config:
        from_attributes = True

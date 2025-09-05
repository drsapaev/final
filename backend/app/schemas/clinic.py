"""
Pydantic схемы для управления клиникой в админ панели
"""
from datetime import datetime, time
from decimal import Decimal
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


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
    specialty: str = Field(..., max_length=100, description="cardiology, dermatology, stomatology")
    cabinet: Optional[str] = Field(None, max_length=20)
    price_default: Optional[Decimal] = Field(None, ge=0)
    start_number_online: int = Field(1, ge=1, le=100)
    max_online_per_day: int = Field(15, ge=1, le=100)
    auto_close_time: Optional[time] = Field(None, description="Время автозакрытия очереди")
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
    breaks: Optional[List[Dict[str, str]]] = Field(None, description='[{"start": "12:00", "end": "13:00"}]')
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
    code: str = Field(..., max_length=50, description="consultation.cardiology, procedure.cosmetology, etc.")
    name_ru: Optional[str] = Field(None, max_length=100)
    name_uz: Optional[str] = Field(None, max_length=100)
    name_en: Optional[str] = Field(None, max_length=100)
    specialty: Optional[str] = Field(None, max_length=100, description="cardiology, dermatology, stomatology")
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
    queue_start_hour: int = Field(7, ge=0, le=23, description="Час начала онлайн очереди")
    auto_close_time: str = Field("09:00", description="Время автозакрытия")
    
    # Настройки по специальностям
    start_numbers: Dict[str, int] = Field(
        default={
            "cardiology": 1,
            "dermatology": 15,
            "stomatology": 3
        },
        description="Стартовые номера по специальностям"
    )
    
    max_per_day: Dict[str, int] = Field(
        default={
            "cardiology": 15,
            "dermatology": 20,
            "stomatology": 12
        },
        description="Максимум онлайн записей в день"
    )


class QueueTestRequest(BaseModel):
    """Запрос на тестирование очереди"""
    doctor_id: int
    date: Optional[str] = None  # YYYY-MM-DD format

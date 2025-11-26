"""
Pydantic схемы для онлайн-очереди согласно detail.md
"""
from datetime import datetime, date
from typing import Optional, List
from pydantic import BaseModel, Field, ConfigDict


# ===================== QR ТОКЕНЫ =====================

class QRTokenRequest(BaseModel):
    """Запрос на генерацию QR токена"""
    day: date = Field(..., description="Дата в формате YYYY-MM-DD")
    specialist_id: int = Field(..., description="ID врача/специалиста")


class QRTokenResponse(BaseModel):
    """Ответ с QR токеном"""
    token: str = Field(..., description="Уникальный токен для QR")
    qr_url: str = Field(..., description="URL для QR кода")
    specialist_name: str = Field(..., description="Имя специалиста")
    specialty: str = Field(..., description="Специальность")
    cabinet: Optional[str] = Field(None, description="Номер кабинета")
    day: date = Field(..., description="Дата приема")
    start_time: str = Field(..., description="Время начала онлайн-записи")
    max_slots: int = Field(..., description="Максимум мест в очереди")
    current_count: int = Field(0, description="Текущее количество записавшихся")


# ===================== ВСТУПЛЕНИЕ В ОЧЕРЕДЬ =====================

class QueueJoinRequest(BaseModel):
    """Запрос на вступление в очередь"""
    token: str = Field(..., description="Токен из QR кода")
    phone: Optional[str] = Field(None, description="Номер телефона")
    telegram_id: Optional[int] = Field(None, description="ID Telegram чата")
    patient_name: Optional[str] = Field(None, description="Имя пациента")


class QueueJoinResponse(BaseModel):
    """Ответ на вступление в очередь"""
    success: bool = Field(..., description="Успешность операции")
    number: Optional[int] = Field(None, description="Номер в очереди")
    duplicate: bool = Field(False, description="Повторная запись (тот же номер)")
    message: str = Field(..., description="Сообщение пользователю")
    
    # Дополнительная информация
    specialist_name: Optional[str] = None
    cabinet: Optional[str] = None
    estimated_time: Optional[str] = None  # Примерное время приема


class QueueJoinError(BaseModel):
    """Ошибка вступления в очередь"""
    success: bool = Field(False)
    error_code: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Сообщение об ошибке")
    
    # Дополнительная информация
    queue_closed: bool = Field(False, description="Очередь закрыта")
    queue_full: bool = Field(False, description="Очередь переполнена")
    outside_hours: bool = Field(False, description="Вне рабочих часов")


# ===================== ОТКРЫТИЕ ПРИЕМА =====================

class QueueOpenRequest(BaseModel):
    """Запрос на открытие приема"""
    day: date = Field(..., description="Дата")
    specialist_id: int = Field(..., description="ID специалиста")


class QueueOpenResponse(BaseModel):
    """Ответ на открытие приема"""
    success: bool = Field(..., description="Успешность операции")
    message: str = Field(..., description="Сообщение")
    opened_at: datetime = Field(..., description="Время открытия")
    online_entries_count: int = Field(..., description="Количество онлайн-записей")
    closed_online_registration: bool = Field(..., description="Онлайн-набор закрыт")


# ===================== СОСТОЯНИЕ ОЧЕРЕДИ =====================

class QueueEntryOut(BaseModel):
    """Запись в очереди"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    number: int
    patient_name: Optional[str] = None
    phone: Optional[str] = None
    source: str
    status: str
    created_at: datetime
    called_at: Optional[datetime] = None


class DailyQueueOut(BaseModel):
    """Состояние дневной очереди"""
    model_config = ConfigDict(from_attributes=True)
    
    id: int
    day: date
    specialist_id: int
    active: bool
    opened_at: Optional[datetime] = None
    created_at: datetime
    
    # Связанные данные
    specialist: Optional[dict] = None
    entries: List[QueueEntryOut] = []
    
    # Статистика
    total_entries: int = 0
    waiting_count: int = 0
    served_count: int = 0


# ===================== НАСТРОЙКИ ОЧЕРЕДИ =====================

class QueueSettings(BaseModel):
    """Настройки очереди из админ панели"""
    timezone: str = Field("Asia/Tashkent", description="Часовой пояс")
    queue_start_hour: int = Field(7, ge=0, le=23, description="Час начала (07:00)")
    auto_close_time: Optional[str] = Field("09:00", description="Время автозакрытия")
    
    # По специальностям
    start_numbers: dict = Field(
        default={
            "cardiology": 1,
            "dermatology": 15,
            "stomatology": 3
        },
        description="Стартовые номера по специальностям"
    )
    
    max_per_day: dict = Field(
        default={
            "cardiology": 15,
            "dermatology": 20,
            "stomatology": 12
        },
        description="Максимум записей в день"
    )


# ===================== СТАТУС ПРОВЕРКИ =====================

class QueueStatusCheck(BaseModel):
    """Проверка статуса очереди"""
    queue_open: bool = Field(..., description="Очередь открыта")
    within_hours: bool = Field(..., description="В рабочих часах")
    has_slots: bool = Field(..., description="Есть свободные места")
    current_time: datetime = Field(..., description="Текущее время")
    queue_start_time: str = Field(..., description="Время начала очереди")
    opened_at: Optional[datetime] = Field(None, description="Время открытия приема")

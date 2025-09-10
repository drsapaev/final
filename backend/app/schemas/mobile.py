"""
Схемы для мобильного API
"""
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class MobileLoginRequest(BaseModel):
    """Запрос мобильной аутентификации"""
    model_config = ConfigDict(protected_namespaces=())
    
    phone: str = Field(..., description="Номер телефона")
    password: Optional[str] = Field(None, description="Пароль (опционально)")
    telegram_id: Optional[str] = Field(None, description="Telegram ID")
    device_token: Optional[str] = Field(None, description="Токен устройства для push-уведомлений")


class MobileLoginResponse(BaseModel):
    """Ответ мобильной аутентификации"""
    model_config = ConfigDict(protected_namespaces=())
    
    access_token: str = Field(..., description="JWT токен")
    token_type: str = Field(default="bearer", description="Тип токена")
    expires_in: int = Field(..., description="Время жизни токена в секундах")
    user: Dict[str, Any] = Field(..., description="Информация о пользователе")
    permissions: List[str] = Field(default_factory=list, description="Разрешения пользователя")


class MobilePatientProfile(BaseModel):
    """Профиль пациента для мобильного приложения"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    name: str
    phone: str
    birth_year: Optional[int] = None
    address: Optional[str] = None
    telegram_id: Optional[str] = None
    created_at: datetime
    last_visit: Optional[datetime] = None
    total_visits: int = 0
    upcoming_appointments: int = 0


class PatientProfileOut(BaseModel):
    """Профиль пациента для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    fio: str
    phone: str
    birth_year: Optional[int] = None
    address: Optional[str] = None
    telegram_id: Optional[str] = None
    created_at: datetime


class MobileAppointmentSummary(BaseModel):
    """Краткая информация о записи для мобильного приложения"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    doctor_name: str
    doctor_specialty: str
    appointment_date: datetime
    status: str
    total_cost: Optional[float] = None
    services: List[str] = Field(default_factory=list)
    can_cancel: bool = True
    can_reschedule: bool = True


class MobileAppointmentDetail(BaseModel):
    """Детальная информация о записи"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    doctor_name: str
    doctor_specialty: str
    doctor_phone: Optional[str] = None
    appointment_date: datetime
    status: str
    complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    total_cost: Optional[float] = None
    services: List[Dict[str, Any]] = Field(default_factory=list)
    payment_status: str
    can_cancel: bool = True
    can_reschedule: bool = True
    notes: Optional[str] = None


class MobileBookAppointmentRequest(BaseModel):
    """Запрос на запись к врачу"""
    model_config = ConfigDict(protected_namespaces=())
    
    doctor_id: int = Field(..., description="ID врача")
    preferred_date: str = Field(..., description="Предпочтительная дата (YYYY-MM-DD)")
    preferred_time: Optional[str] = Field(None, description="Предпочтительное время (HH:MM)")
    complaint: Optional[str] = Field(None, description="Жалобы")
    services: List[int] = Field(default_factory=list, description="ID услуг")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")


class MobileBookAppointmentResponse(BaseModel):
    """Ответ на запись к врачу"""
    model_config = ConfigDict(protected_namespaces=())
    
    appointment_id: int
    appointment_date: datetime
    doctor_name: str
    doctor_specialty: str
    total_cost: float
    status: str
    confirmation_code: Optional[str] = None
    payment_required: bool = False
    payment_url: Optional[str] = None


class MobileQueueRequest(BaseModel):
    """Запрос на запись в очередь"""
    model_config = ConfigDict(protected_namespaces=())
    
    specialty: str = Field(..., description="Специализация")
    services: List[int] = Field(default_factory=list, description="ID услуг")
    notes: Optional[str] = Field(None, description="Дополнительные заметки")


class MobileQueueResponse(BaseModel):
    """Ответ на запись в очередь"""
    model_config = ConfigDict(protected_namespaces=())
    
    queue_id: int
    queue_number: int
    specialty: str
    estimated_wait_time: Optional[int] = None  # в минутах
    status: str
    position_in_queue: int
    can_cancel: bool = True


class MobileLabResult(BaseModel):
    """Результат анализа для мобильного приложения"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    test_name: str
    result: str
    normal_range: Optional[str] = None
    status: str  # normal, abnormal, critical
    test_date: datetime
    doctor_notes: Optional[str] = None
    file_url: Optional[str] = None  # PDF с результатами


class MobilePaymentRequest(BaseModel):
    """Запрос на оплату"""
    model_config = ConfigDict(protected_namespaces=())
    
    appointment_id: int
    amount: float
    payment_method: str  # card, payme, click
    description: Optional[str] = None


class MobilePaymentResponse(BaseModel):
    """Ответ на запрос оплаты"""
    model_config = ConfigDict(protected_namespaces=())
    
    payment_id: int
    payment_url: str
    amount: float
    currency: str = "UZS"
    status: str
    expires_at: datetime


class MobileNotificationSettings(BaseModel):
    """Настройки уведомлений для мобильного приложения"""
    model_config = ConfigDict(protected_namespaces=())
    
    appointment_reminders: bool = True
    queue_updates: bool = True
    lab_results: bool = True
    payment_notifications: bool = True
    push_enabled: bool = True
    email_enabled: bool = False
    sms_enabled: bool = False


class MobileQuickStats(BaseModel):
    """Быстрая статистика для мобильного приложения"""
    model_config = ConfigDict(protected_namespaces=())
    
    total_appointments: int = 0
    upcoming_appointments: int = 0
    completed_appointments: int = 0
    total_spent: float = 0.0
    last_visit: Optional[datetime] = None
    favorite_doctor: Optional[str] = None
    pending_payments: int = 0


class MobileErrorResponse(BaseModel):
    """Стандартный ответ об ошибке для мобильного API"""
    model_config = ConfigDict(protected_namespaces=())
    
    error: str = Field(..., description="Код ошибки")
    message: str = Field(..., description="Сообщение об ошибке")
    details: Optional[Dict[str, Any]] = Field(None, description="Дополнительные детали")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class MobileSuccessResponse(BaseModel):
    """Стандартный ответ об успехе для мобильного API"""
    model_config = ConfigDict(protected_namespaces=())
    
    success: bool = Field(default=True)
    message: str = Field(..., description="Сообщение об успехе")
    data: Optional[Dict[str, Any]] = Field(None, description="Данные ответа")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


# === ДОПОЛНИТЕЛЬНЫЕ СХЕМЫ ДЛЯ API ===

class AppointmentUpcomingOut(BaseModel):
    """Предстоящие записи для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    doctor_name: str
    specialty: str
    appointment_date: datetime
    status: str
    clinic_address: str


class BookAppointmentRequest(BaseModel):
    """Запрос на запись к врачу для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    doctor_id: int = Field(..., description="ID врача")
    appointment_date: datetime = Field(..., description="Дата записи")
    specialty: str = Field(..., description="Специализация")
    patient_id: Optional[int] = Field(None, description="ID пациента")
    patient_fio: Optional[str] = Field(None, description="ФИО пациента")
    patient_phone: Optional[str] = Field(None, description="Телефон пациента")


class LabResultOut(BaseModel):
    """Результаты анализов для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    test_name: str
    result_value: str
    reference_range: str
    unit: str
    result_date: datetime
    status: str
    notes: Optional[str] = None


class MobileNotificationOut(BaseModel):
    """Уведомления для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    title: str
    message: str
    created_at: datetime
    read: bool
    type: str


class MobileNotificationCreate(BaseModel):
    """Создание уведомления для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    user_id: int
    title: str
    message: str
    type: str


class MobileAppointmentDetailOut(BaseModel):
    """Детали записи для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    patient_id: int
    doctor_id: int
    doctor_name: str
    specialty: str
    appointment_date: datetime
    status: str
    complaint: Optional[str] = None
    diagnosis: Optional[str] = None
    total_cost: Optional[float] = None
    created_at: datetime
    updated_at: datetime


class MobileVisitDetailOut(BaseModel):
    """Детали визита для API"""
    model_config = ConfigDict(protected_namespaces=())
    
    id: int
    appointment_id: int
    patient_id: int
    doctor_id: int
    doctor_name: str
    visit_date: datetime
    status: str
    diagnosis: Optional[str] = None
    prescription: Optional[str] = None
    recommendations: Optional[str] = None
    total_cost: Optional[float] = None
    created_at: datetime
    updated_at: datetime

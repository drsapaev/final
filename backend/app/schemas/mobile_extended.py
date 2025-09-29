"""
Расширенные схемы для мобильного API
"""
from datetime import datetime, date
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class DoctorSearchResponse(BaseModel):
    """Ответ поиска врачей"""
    id: int
    name: str
    specialty: str
    experience_years: Optional[int] = None
    education: Optional[str] = None
    photo_url: Optional[str] = None
    rating: float = 0.0
    total_patients: int = 0
    available_today: bool = False
    next_available_slot: Optional[datetime] = None
    consultation_fee: float = 0.0


class ServiceSearchResponse(BaseModel):
    """Ответ поиска услуг"""
    id: int
    name: str
    description: Optional[str] = None
    category: str
    price: float
    duration_minutes: Optional[int] = None
    requires_preparation: bool = False
    preparation_instructions: Optional[str] = None
    available_doctors: int = 0


class ServiceCategoryResponse(BaseModel):
    """Категория услуг"""
    name: str
    display_name: str
    description: Optional[str] = None
    icon: Optional[str] = None
    services_count: int = 0
    average_price: Optional[float] = None


class QueuePositionResponse(BaseModel):
    """Позиция в очереди"""
    queue_id: int
    doctor_name: str
    specialty: str
    my_number: int
    current_number: int
    patients_before_me: int
    estimated_wait_minutes: int
    status: str  # waiting, ready


class FeedbackResponse(BaseModel):
    """Ответ на обратную связь"""
    success: bool
    message: str
    feedback_id: int


class EmergencyContactResponse(BaseModel):
    """Ответ экстренного обращения"""
    success: bool
    message: str
    emergency_id: int
    contacts: Dict[str, Dict[str, str]]


class ProfileResponse(BaseModel):
    """Ответ обновления профиля"""
    success: bool
    message: str
    patient: Dict[str, Any]


class NotificationSettingsResponse(BaseModel):
    """Настройки уведомлений"""
    push_enabled: bool = True
    sms_enabled: bool = True
    email_enabled: bool = True
    appointment_reminders: bool = True
    lab_results: bool = True
    promotions: bool = False


class ClinicInfoResponse(BaseModel):
    """Информация о клинике"""
    name: str
    address: str
    phone: str
    email: str
    website: str
    working_hours: Dict[str, str]
    services: List[str]
    emergency_phone: str
    location: Dict[str, float]


class APIVersionResponse(BaseModel):
    """Версия API"""
    version: str
    build: str
    features: List[str]
    last_updated: str


class AppointmentActionResponse(BaseModel):
    """Ответ действия с записью"""
    success: bool
    message: str
    new_date: Optional[str] = None


class DoctorScheduleSlot(BaseModel):
    """Слот в расписании врача"""
    date: date
    time: str
    available: bool
    appointment_id: Optional[int] = None
    patient_name: Optional[str] = None


class DoctorScheduleResponse(BaseModel):
    """Расписание врача"""
    doctor_id: int
    schedule: List[DoctorScheduleSlot]


class MobileStatsExtended(BaseModel):
    """Расширенная статистика для мобильного"""
    total_appointments: int = 0
    upcoming_appointments: int = 0
    completed_appointments: int = 0
    cancelled_appointments: int = 0
    total_spent: float = 0.0
    last_visit: Optional[datetime] = None
    favorite_doctor: Optional[str] = None
    pending_payments: int = 0
    average_rating_given: Optional[float] = None
    loyalty_points: int = 0


class MobileNotificationExtended(BaseModel):
    """Расширенное уведомление"""
    id: int
    title: str
    message: str
    type: str  # appointment, lab_result, promotion, system
    created_at: datetime
    read_at: Optional[datetime] = None
    data: Optional[Dict[str, Any]] = None
    priority: str = "normal"  # low, normal, high, urgent
    action_url: Optional[str] = None


class PatientMedicalHistory(BaseModel):
    """Медицинская история пациента"""
    allergies: Optional[str] = None
    chronic_conditions: Optional[str] = None
    medications: List[str] = []
    previous_surgeries: List[str] = []
    family_history: Optional[str] = None
    blood_type: Optional[str] = None
    emergency_contact: Optional[str] = None


class AppointmentReminderSettings(BaseModel):
    """Настройки напоминаний о записях"""
    enabled: bool = True
    remind_24h: bool = True
    remind_2h: bool = True
    remind_30min: bool = False
    method: str = "push"  # push, sms, email, all


class MobileSecuritySettings(BaseModel):
    """Настройки безопасности мобильного приложения"""
    biometric_enabled: bool = False
    pin_enabled: bool = False
    auto_logout_minutes: int = 30
    require_pin_for_payments: bool = True
    two_factor_enabled: bool = False


class PaymentMethodMobile(BaseModel):
    """Способ оплаты для мобильного"""
    id: int
    type: str  # card, cash, click, payme, kaspi
    name: str
    details: Optional[str] = None  # Последние 4 цифры карты и т.д.
    is_default: bool = False
    expires_at: Optional[date] = None


class MobilePaymentRequest(BaseModel):
    """Запрос оплаты через мобильное"""
    appointment_id: int
    payment_method_id: int
    amount: float
    currency: str = "UZS"


class MobilePaymentResponse(BaseModel):
    """Ответ оплаты через мобильное"""
    success: bool
    payment_id: Optional[int] = None
    payment_url: Optional[str] = None  # Для онлайн оплаты
    message: str
    status: str  # pending, completed, failed


class LabResultExtended(BaseModel):
    """Расширенный результат анализа"""
    id: int
    test_name: str
    result_value: str
    reference_range: Optional[str] = None
    unit: Optional[str] = None
    result_date: datetime
    status: str  # pending, ready, reviewed
    notes: Optional[str] = None
    doctor_comments: Optional[str] = None
    abnormal: bool = False
    critical: bool = False
    file_url: Optional[str] = None  # PDF результата


class MobileSearchFilters(BaseModel):
    """Фильтры поиска для мобильного"""
    specialty: Optional[str] = None
    rating_min: Optional[float] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None
    available_today: Optional[bool] = None
    location: Optional[str] = None
    insurance_accepted: Optional[bool] = None



"""
Расширенные схемы для мобильного API
"""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


class DoctorSearchResponse(BaseModel):
    """Ответ поиска врачей"""

    id: int
    name: str
    specialty: str
    experience_years: int | None = None
    education: str | None = None
    photo_url: str | None = None
    rating: float = 0.0
    total_patients: int = 0
    available_today: bool = False
    next_available_slot: datetime | None = None
    consultation_fee: float = 0.0


class ServiceSearchResponse(BaseModel):
    """Ответ поиска услуг"""

    id: int
    name: str
    description: str | None = None
    category: str
    price: float
    duration_minutes: int | None = None
    requires_preparation: bool = False
    preparation_instructions: str | None = None
    available_doctors: int = 0


class ServiceCategoryResponse(BaseModel):
    """Категория услуг"""

    name: str
    display_name: str
    description: str | None = None
    icon: str | None = None
    services_count: int = 0
    average_price: float | None = None


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
    contacts: dict[str, dict[str, str]]


class ProfileResponse(BaseModel):
    """Ответ обновления профиля"""

    success: bool
    message: str
    patient: dict[str, Any]


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
    working_hours: dict[str, str]
    services: list[str]
    emergency_phone: str
    location: dict[str, float]


class APIVersionResponse(BaseModel):
    """Версия API"""

    version: str
    build: str
    features: list[str]
    last_updated: str


class AppointmentActionResponse(BaseModel):
    """Ответ действия с записью"""

    success: bool
    message: str
    new_date: str | None = None


class DoctorScheduleSlot(BaseModel):
    """Слот в расписании врача"""

    date: date
    time: str
    available: bool
    appointment_id: int | None = None
    patient_name: str | None = None


class DoctorScheduleResponse(BaseModel):
    """Расписание врача"""

    doctor_id: int
    schedule: list[DoctorScheduleSlot]


class MobileStatsExtended(BaseModel):
    """Расширенная статистика для мобильного"""

    total_appointments: int = 0
    upcoming_appointments: int = 0
    completed_appointments: int = 0
    cancelled_appointments: int = 0
    total_spent: float = 0.0
    last_visit: datetime | None = None
    favorite_doctor: str | None = None
    pending_payments: int = 0
    average_rating_given: float | None = None
    loyalty_points: int = 0


class MobileNotificationExtended(BaseModel):
    """Расширенное уведомление"""

    id: int
    title: str
    message: str
    type: str  # appointment, lab_result, promotion, system
    created_at: datetime
    read_at: datetime | None = None
    data: dict[str, Any] | None = None
    priority: str = "normal"  # low, normal, high, urgent
    action_url: str | None = None


class PatientMedicalHistory(BaseModel):
    """Медицинская история пациента"""

    allergies: str | None = None
    chronic_conditions: str | None = None
    medications: list[str] = []
    previous_surgeries: list[str] = []
    family_history: str | None = None
    blood_type: str | None = None
    emergency_contact: str | None = None


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
    details: str | None = None  # Последние 4 цифры карты и т.д.
    is_default: bool = False
    expires_at: date | None = None


class MobilePaymentRequest(BaseModel):
    """Запрос оплаты через мобильное"""

    appointment_id: int
    payment_method_id: int
    amount: float
    currency: str = "UZS"


class MobilePaymentResponse(BaseModel):
    """Ответ оплаты через мобильное"""

    success: bool
    payment_id: int | None = None
    payment_url: str | None = None  # Для онлайн оплаты
    message: str
    status: str  # pending, completed, failed


class LabResultExtended(BaseModel):
    """Расширенный результат анализа"""

    id: int
    test_name: str
    result_value: str
    reference_range: str | None = None
    unit: str | None = None
    result_date: datetime
    status: str  # pending, ready, reviewed
    notes: str | None = None
    doctor_comments: str | None = None
    abnormal: bool = False
    critical: bool = False
    file_url: str | None = None  # PDF результата


class MobileSearchFilters(BaseModel):
    """Фильтры поиска для мобильного"""

    specialty: str | None = None
    rating_min: float | None = None
    price_min: float | None = None
    price_max: float | None = None
    available_today: bool | None = None
    location: str | None = None
    insurance_accepted: bool | None = None

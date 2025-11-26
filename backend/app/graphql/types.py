"""
GraphQL типы для API клиники
"""
import strawberry
from typing import List, Optional
from datetime import datetime, date, time
from decimal import Decimal


@strawberry.type
class UserType:
    """Тип пользователя"""
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


@strawberry.type
class PatientType:
    """Тип пациента"""
    id: int
    full_name: str
    phone: str
    email: Optional[str] = None
    birth_date: Optional[date] = None
    address: Optional[str] = None
    passport_series: Optional[str] = None
    passport_number: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@strawberry.type
class DoctorType:
    """Тип врача"""
    id: int
    user: Optional[UserType] = None
    specialty: str
    cabinet: Optional[str] = None
    price_default: Optional[float] = None
    start_number_online: int
    max_online_per_day: int
    auto_close_time: Optional[time] = None
    active: bool
    created_at: datetime
    updated_at: datetime


@strawberry.type
class ServiceType:
    """Тип услуги"""
    id: int
    name: str
    code: str
    price: float
    category: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    doctor: Optional[DoctorType] = None
    active: bool
    created_at: datetime
    updated_at: datetime


@strawberry.type
class AppointmentType:
    """Тип записи"""
    id: int
    patient: PatientType
    doctor: DoctorType
    service: ServiceType
    appointment_date: datetime
    status: str
    notes: Optional[str] = None
    payment_status: str
    payment_amount: Optional[float] = None
    created_at: datetime
    updated_at: datetime


@strawberry.type
class VisitType:
    """Тип визита"""
    id: int
    patient: PatientType
    doctor: DoctorType
    visit_date: date
    visit_time: Optional[time] = None
    status: str
    discount_mode: Optional[str] = None
    all_free: bool
    total_amount: Optional[float] = None
    payment_status: str
    created_at: datetime
    updated_at: datetime


@strawberry.type
class VisitServiceType:
    """Тип услуги в визите"""
    id: int
    visit: VisitType
    service: ServiceType
    price: float
    quantity: int
    total_price: float
    created_at: datetime


@strawberry.type
class QueueEntryType:
    """Тип записи в очереди"""
    id: int
    patient: PatientType
    doctor: DoctorType
    queue_number: int
    status: str
    created_at: datetime
    called_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@strawberry.type
class DailyQueueType:
    """Тип дневной очереди"""
    id: int
    doctor: DoctorType
    queue_date: date
    queue_tag: Optional[str] = None
    current_number: int
    last_called_number: int
    is_active: bool
    cabinet_number: Optional[str] = None
    cabinet_floor: Optional[str] = None
    cabinet_building: Optional[str] = None
    created_at: datetime
    updated_at: datetime


@strawberry.type
class ClinicSettingsType:
    """Тип настроек клиники"""
    id: int
    key: str
    value: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    updated_at: datetime
    created_at: datetime


# ===================== INPUT TYPES =====================

@strawberry.input
class PatientInput:
    """Входные данные для создания пациента"""
    full_name: str
    phone: str
    email: Optional[str] = None
    birth_date: Optional[date] = None
    address: Optional[str] = None
    passport_series: Optional[str] = None
    passport_number: Optional[str] = None


@strawberry.input
class PatientUpdateInput:
    """Входные данные для обновления пациента"""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    birth_date: Optional[date] = None
    address: Optional[str] = None
    passport_series: Optional[str] = None
    passport_number: Optional[str] = None


@strawberry.input
class AppointmentInput:
    """Входные данные для создания записи"""
    patient_id: int
    doctor_id: int
    service_id: int
    appointment_date: datetime
    notes: Optional[str] = None


@strawberry.input
class VisitInput:
    """Входные данные для создания визита"""
    patient_id: int
    doctor_id: int
    visit_date: date
    visit_time: Optional[time] = None
    discount_mode: Optional[str] = None
    all_free: bool = False
    service_ids: List[int]


@strawberry.input
class ServiceInput:
    """Входные данные для создания услуги"""
    name: str
    code: str
    price: float
    category: Optional[str] = None
    description: Optional[str] = None
    duration_minutes: Optional[int] = None
    doctor_id: Optional[int] = None


@strawberry.input
class DoctorInput:
    """Входные данные для создания врача"""
    user_id: Optional[int] = None
    specialty: str
    cabinet: Optional[str] = None
    price_default: Optional[float] = None
    max_online_per_day: int = 15


@strawberry.input
class QueueEntryInput:
    """Входные данные для создания записи в очереди"""
    patient_id: int
    doctor_id: int
    queue_tag: Optional[str] = None


# ===================== FILTER TYPES =====================

@strawberry.input
class PatientFilter:
    """Фильтр для пациентов"""
    full_name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    created_after: Optional[datetime] = None
    created_before: Optional[datetime] = None


@strawberry.input
class AppointmentFilter:
    """Фильтр для записей"""
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    service_id: Optional[int] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None


@strawberry.input
class VisitFilter:
    """Фильтр для визитов"""
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: Optional[str] = None
    payment_status: Optional[str] = None
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    discount_mode: Optional[str] = None
    all_free: Optional[bool] = None


@strawberry.input
class ServiceFilter:
    """Фильтр для услуг"""
    name: Optional[str] = None
    code: Optional[str] = None
    category: Optional[str] = None
    doctor_id: Optional[int] = None
    active: Optional[bool] = None
    price_min: Optional[float] = None
    price_max: Optional[float] = None


@strawberry.input
class DoctorFilter:
    """Фильтр для врачей"""
    specialty: Optional[str] = None
    cabinet: Optional[str] = None
    active: Optional[bool] = None


@strawberry.input
class QueueFilter:
    """Фильтр для очередей"""
    doctor_id: Optional[int] = None
    queue_date: Optional[date] = None
    status: Optional[str] = None
    queue_tag: Optional[str] = None


# ===================== PAGINATION =====================

@strawberry.input
class PaginationInput:
    """Пагинация"""
    page: int = 1
    per_page: int = 20


@strawberry.type
class PaginationInfo:
    """Информация о пагинации"""
    page: int
    per_page: int
    total: int
    pages: int
    has_next: bool
    has_prev: bool


@strawberry.type
class PaginatedPatients:
    """Пагинированный список пациентов"""
    items: List[PatientType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedAppointments:
    """Пагинированный список записей"""
    items: List[AppointmentType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedVisits:
    """Пагинированный список визитов"""
    items: List[VisitType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedServices:
    """Пагинированный список услуг"""
    items: List[ServiceType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedDoctors:
    """Пагинированный список врачей"""
    items: List[DoctorType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedQueueEntries:
    """Пагинированный список записей в очереди"""
    items: List[QueueEntryType]
    pagination: PaginationInfo


# ===================== STATISTICS TYPES =====================

@strawberry.type
class AppointmentStats:
    """Статистика записей"""
    total: int
    today: int
    this_week: int
    this_month: int
    by_status: List[str]
    by_payment_status: List[str]


@strawberry.type
class VisitStats:
    """Статистика визитов"""
    total: int
    today: int
    this_week: int
    this_month: int
    by_status: List[str]
    by_discount_mode: List[str]
    total_revenue: float


@strawberry.type
class QueueStats:
    """Статистика очередей"""
    total_entries: int
    active_queues: int
    average_wait_time: float
    completed_today: int
    pending_today: int


@strawberry.type
class DoctorStats:
    """Статистика врача"""
    total_appointments: int
    total_visits: int
    today_appointments: int
    today_visits: int
    average_rating: Optional[float] = None
    total_revenue: float


# ===================== RESPONSE TYPES =====================

@strawberry.type
class MutationResponse:
    """Базовый ответ мутации"""
    success: bool
    message: str
    errors: Optional[List[str]] = None


@strawberry.type
class PatientMutationResponse(MutationResponse):
    """Ответ мутации пациента"""
    patient: Optional[PatientType] = None


@strawberry.type
class AppointmentMutationResponse(MutationResponse):
    """Ответ мутации записи"""
    appointment: Optional[AppointmentType] = None


@strawberry.type
class VisitMutationResponse(MutationResponse):
    """Ответ мутации визита"""
    visit: Optional[VisitType] = None


@strawberry.type
class ServiceMutationResponse(MutationResponse):
    """Ответ мутации услуги"""
    service: Optional[ServiceType] = None


@strawberry.type
class DoctorMutationResponse(MutationResponse):
    """Ответ мутации врача"""
    doctor: Optional[DoctorType] = None


@strawberry.type
class QueueMutationResponse(MutationResponse):
    """Ответ мутации очереди"""
    queue_entry: Optional[QueueEntryType] = None


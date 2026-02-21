"""
GraphQL типы для API клиники
"""

from datetime import date, datetime, time

import strawberry


@strawberry.type
class UserType:
    """Тип пользователя"""

    id: int
    username: str
    email: str
    full_name: str | None = None
    phone: str | None = None
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
    email: str | None = None
    birth_date: date | None = None
    address: str | None = None
    passport_series: str | None = None
    passport_number: str | None = None
    created_at: datetime
    updated_at: datetime


@strawberry.type
class DoctorType:
    """Тип врача"""

    id: int
    user: UserType | None = None
    specialty: str
    cabinet: str | None = None
    price_default: float | None = None
    start_number_online: int
    max_online_per_day: int
    auto_close_time: time | None = None
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
    category: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    doctor: DoctorType | None = None
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
    notes: str | None = None
    payment_status: str
    payment_amount: float | None = None
    created_at: datetime
    updated_at: datetime


@strawberry.type
class VisitType:
    """Тип визита"""

    id: int
    patient: PatientType
    doctor: DoctorType
    visit_date: date
    visit_time: time | None = None
    status: str
    discount_mode: str | None = None
    all_free: bool
    total_amount: float | None = None
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
    called_at: datetime | None = None
    completed_at: datetime | None = None


@strawberry.type
class DailyQueueType:
    """Тип дневной очереди"""

    id: int
    doctor: DoctorType
    queue_date: date
    queue_tag: str | None = None
    current_number: int
    last_called_number: int
    is_active: bool
    cabinet_number: str | None = None
    cabinet_floor: str | None = None
    cabinet_building: str | None = None
    created_at: datetime
    updated_at: datetime


@strawberry.type
class ClinicSettingsType:
    """Тип настроек клиники"""

    id: int
    key: str
    value: str | None = None
    category: str | None = None
    description: str | None = None
    updated_at: datetime
    created_at: datetime


# ===================== INPUT TYPES =====================


@strawberry.input
class PatientInput:
    """Входные данные для создания пациента"""

    full_name: str
    phone: str
    email: str | None = None
    birth_date: date | None = None
    address: str | None = None
    passport_series: str | None = None
    passport_number: str | None = None


@strawberry.input
class PatientUpdateInput:
    """Входные данные для обновления пациента"""

    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: date | None = None
    address: str | None = None
    passport_series: str | None = None
    passport_number: str | None = None


@strawberry.input
class AppointmentInput:
    """Входные данные для создания записи"""

    patient_id: int
    doctor_id: int
    service_id: int
    appointment_date: datetime
    notes: str | None = None


@strawberry.input
class VisitInput:
    """Входные данные для создания визита"""

    patient_id: int
    doctor_id: int
    visit_date: date
    visit_time: time | None = None
    discount_mode: str | None = None
    all_free: bool = False
    service_ids: list[int]


@strawberry.input
class ServiceInput:
    """Входные данные для создания услуги"""

    name: str
    code: str
    price: float
    category: str | None = None
    description: str | None = None
    duration_minutes: int | None = None
    doctor_id: int | None = None


@strawberry.input
class DoctorInput:
    """Входные данные для создания врача"""

    user_id: int | None = None
    specialty: str
    cabinet: str | None = None
    price_default: float | None = None
    max_online_per_day: int = 15


@strawberry.input
class QueueEntryInput:
    """Входные данные для создания записи в очереди"""

    patient_id: int
    doctor_id: int
    queue_tag: str | None = None


# ===================== FILTER TYPES =====================


@strawberry.input
class PatientFilter:
    """Фильтр для пациентов"""

    full_name: str | None = None
    phone: str | None = None
    email: str | None = None
    created_after: datetime | None = None
    created_before: datetime | None = None


@strawberry.input
class AppointmentFilter:
    """Фильтр для записей"""

    patient_id: int | None = None
    doctor_id: int | None = None
    service_id: int | None = None
    status: str | None = None
    payment_status: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None


@strawberry.input
class VisitFilter:
    """Фильтр для визитов"""

    patient_id: int | None = None
    doctor_id: int | None = None
    status: str | None = None
    payment_status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    discount_mode: str | None = None
    all_free: bool | None = None


@strawberry.input
class ServiceFilter:
    """Фильтр для услуг"""

    name: str | None = None
    code: str | None = None
    category: str | None = None
    doctor_id: int | None = None
    active: bool | None = None
    price_min: float | None = None
    price_max: float | None = None


@strawberry.input
class DoctorFilter:
    """Фильтр для врачей"""

    specialty: str | None = None
    cabinet: str | None = None
    active: bool | None = None


@strawberry.input
class QueueFilter:
    """Фильтр для очередей"""

    doctor_id: int | None = None
    queue_date: date | None = None
    status: str | None = None
    queue_tag: str | None = None


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

    items: list[PatientType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedAppointments:
    """Пагинированный список записей"""

    items: list[AppointmentType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedVisits:
    """Пагинированный список визитов"""

    items: list[VisitType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedServices:
    """Пагинированный список услуг"""

    items: list[ServiceType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedDoctors:
    """Пагинированный список врачей"""

    items: list[DoctorType]
    pagination: PaginationInfo


@strawberry.type
class PaginatedQueueEntries:
    """Пагинированный список записей в очереди"""

    items: list[QueueEntryType]
    pagination: PaginationInfo


# ===================== STATISTICS TYPES =====================


@strawberry.type
class AppointmentStats:
    """Статистика записей"""

    total: int
    today: int
    this_week: int
    this_month: int
    by_status: list[str]
    by_payment_status: list[str]


@strawberry.type
class VisitStats:
    """Статистика визитов"""

    total: int
    today: int
    this_week: int
    this_month: int
    by_status: list[str]
    by_discount_mode: list[str]
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
    average_rating: float | None = None
    total_revenue: float


# ===================== RESPONSE TYPES =====================


@strawberry.type
class MutationResponse:
    """Базовый ответ мутации"""

    success: bool
    message: str
    errors: list[str] | None = None


@strawberry.type
class PatientMutationResponse(MutationResponse):
    """Ответ мутации пациента"""

    patient: PatientType | None = None


@strawberry.type
class AppointmentMutationResponse(MutationResponse):
    """Ответ мутации записи"""

    appointment: AppointmentType | None = None


@strawberry.type
class VisitMutationResponse(MutationResponse):
    """Ответ мутации визита"""

    visit: VisitType | None = None


@strawberry.type
class ServiceMutationResponse(MutationResponse):
    """Ответ мутации услуги"""

    service: ServiceType | None = None


@strawberry.type
class DoctorMutationResponse(MutationResponse):
    """Ответ мутации врача"""

    doctor: DoctorType | None = None


@strawberry.type
class QueueMutationResponse(MutationResponse):
    """Ответ мутации очереди"""

    queue_entry: QueueEntryType | None = None

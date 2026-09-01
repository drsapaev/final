"""
GraphQL типы для API клиники

GQL-AUDIT-28 follow-up: типы выровнены с реальными моделями SQLAlchemy
(ранее резолверы ссылались на несуществующие колонки — full_name,
passport_series, queue_date, current_number и т.д.).
"""

from datetime import date, datetime, time

import strawberry


@strawberry.type
class UserType:
    """Тип пользователя"""

    id: int
    username: str
    full_name: str | None = None
    email: str | None = None
    role: str
    is_active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


@strawberry.type
class PatientType:
    """Тип пациента (Patient: last/first/middle имена, doc_type/doc_number)"""

    id: int
    full_name: str
    phone: str | None = None
    email: str | None = None
    sex: str | None = None
    birth_date: date | None = None
    address: str | None = None
    doc_type: str | None = None
    doc_number: str | None = None
    created_at: datetime | None = None


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
    created_at: datetime | None = None
    updated_at: datetime | None = None


@strawberry.type
class ServiceType:
    """Тип услуги (Service: unit/currency/category_code, без doctor-связи)"""

    id: int
    name: str
    code: str | None = None
    price: float | None = None
    unit: str | None = None
    currency: str | None = None
    category_code: str | None = None
    active: bool
    created_at: datetime | None = None
    updated_at: datetime | None = None


@strawberry.type
class AppointmentType:
    """Тип записи (Appointment: services — JSON-коды, payment_type)"""

    id: int
    patient: PatientType | None = None
    doctor: DoctorType | None = None
    appointment_date: date
    appointment_time: str | None = None
    status: str
    notes: str | None = None
    services: list[str] | None = None
    payment_type: str | None = None
    payment_amount: float | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@strawberry.type
class VisitType:
    """Тип визита (Visit: суммы живут в VisitService, не в самом визите)"""

    id: int
    patient: PatientType | None = None
    doctor: DoctorType | None = None
    visit_date: date | None = None
    visit_time: str | None = None
    status: str
    discount_mode: str | None = None
    notes: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@strawberry.type
class QueueEntryType:
    """Тип записи в очереди (OnlineQueueEntry: queue_id/number, called_at)"""

    id: int
    queue: "DailyQueueType"
    patient: PatientType | None = None
    number: int
    status: str
    source: str | None = None
    queue_time: datetime | None = None
    called_at: datetime | None = None
    created_at: datetime | None = None


@strawberry.type
class DailyQueueType:
    """Тип дневной очереди (DailyQueue: day/specialist_id/active)"""

    id: int
    specialist: DoctorType
    day: date
    queue_tag: str | None = None
    active: bool
    opened_at: datetime | None = None
    cabinet_number: str | None = None
    cabinet_floor: int | None = None
    cabinet_building: str | None = None
    created_at: datetime | None = None


# ===================== INPUT TYPES =====================


@strawberry.input
class PatientInput:
    """Входные данные для создания пациента"""

    last_name: str
    first_name: str
    middle_name: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: date | None = None
    sex: str | None = None
    address: str | None = None
    doc_type: str | None = None
    doc_number: str | None = None


@strawberry.input
class PatientUpdateInput:
    """Входные данные для обновления пациента"""

    last_name: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    phone: str | None = None
    email: str | None = None
    birth_date: date | None = None
    sex: str | None = None
    address: str | None = None
    doc_type: str | None = None
    doc_number: str | None = None


@strawberry.input
class AppointmentInput:
    """Входные данные для создания записи"""

    patient_id: int
    doctor_id: int | None = None
    appointment_date: date
    appointment_time: str | None = None
    notes: str | None = None
    services: list[str] | None = None


@strawberry.input
class VisitInput:
    """Входные данные для создания визита"""

    patient_id: int
    doctor_id: int | None = None
    visit_date: date | None = None
    visit_time: str | None = None
    discount_mode: str | None = None
    notes: str | None = None
    service_ids: list[int] | None = None


@strawberry.input
class ServiceInput:
    """Входные данные для создания услуги"""

    name: str
    code: str | None = None
    price: float | None = None
    unit: str | None = None
    currency: str | None = None
    category_code: str | None = None


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
    status: str | None = None
    payment_type: str | None = None
    date_from: date | None = None
    date_to: date | None = None


@strawberry.input
class VisitFilter:
    """Фильтр для визитов"""

    patient_id: int | None = None
    doctor_id: int | None = None
    status: str | None = None
    date_from: date | None = None
    date_to: date | None = None
    discount_mode: str | None = None


@strawberry.input
class ServiceFilter:
    """Фильтр для услуг"""

    name: str | None = None
    code: str | None = None
    category_code: str | None = None
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

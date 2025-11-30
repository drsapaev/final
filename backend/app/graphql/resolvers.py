"""
GraphQL резолверы для API клиники
"""

from datetime import date, datetime
from typing import List, Optional

import strawberry
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.crud import (
    appointment as crud_appointment,
    clinic as crud_clinic,
    patient as crud_patient,
    service as crud_service,
    visit as crud_visit,
)
from app.db.session import get_db
from app.graphql.types import (
    AppointmentFilter,
    AppointmentInput,
    AppointmentMutationResponse,
    AppointmentStats,
    AppointmentType,
    ClinicSettingsType,
    DailyQueueType,
    DoctorFilter,
    DoctorInput,
    DoctorMutationResponse,
    DoctorStats,
    DoctorType,
    PaginatedAppointments,
    PaginatedDoctors,
    PaginatedPatients,
    PaginatedQueueEntries,
    PaginatedServices,
    PaginatedVisits,
    PaginationInfo,
    PaginationInput,
    PatientFilter,
    PatientInput,
    PatientMutationResponse,
    PatientType,
    PatientUpdateInput,
    QueueEntryInput,
    QueueEntryType,
    QueueFilter,
    QueueMutationResponse,
    QueueStats,
    ServiceFilter,
    ServiceInput,
    ServiceMutationResponse,
    ServiceType,
    UserType,
    VisitFilter,
    VisitInput,
    VisitMutationResponse,
    VisitServiceType,
    VisitStats,
    VisitType,
)
from app.models.appointment import Appointment
from app.models.clinic import ClinicSettings, Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService


def get_db_session() -> Session:
    """Получить сессию базы данных"""
    return next(get_db())


# ===================== UTILITY FUNCTIONS =====================


def create_pagination_info(page: int, per_page: int, total: int) -> PaginationInfo:
    """Создать информацию о пагинации"""
    pages = (total + per_page - 1) // per_page
    return PaginationInfo(
        page=page,
        per_page=per_page,
        total=total,
        pages=pages,
        has_next=page < pages,
        has_prev=page > 1,
    )


def apply_pagination(query, page: int, per_page: int):
    """Применить пагинацию к запросу"""
    offset = (page - 1) * per_page
    return query.offset(offset).limit(per_page)


# ===================== CONVERTERS =====================


def user_to_type(user: User) -> UserType:
    """Конвертировать User в UserType"""
    return UserType(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        phone=getattr(user, 'phone', None),
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def patient_to_type(patient: Patient) -> PatientType:
    """Конвертировать Patient в PatientType"""
    return PatientType(
        id=patient.id,
        full_name=patient.full_name,
        phone=patient.phone,
        email=patient.email,
        birth_date=patient.birth_date,
        address=patient.address,
        passport_series=patient.passport_series,
        passport_number=patient.passport_number,
        created_at=patient.created_at,
        updated_at=patient.updated_at,
    )


def doctor_to_type(doctor: Doctor) -> DoctorType:
    """Конвертировать Doctor в DoctorType"""
    return DoctorType(
        id=doctor.id,
        user=user_to_type(doctor.user) if doctor.user else None,
        specialty=doctor.specialty,
        cabinet=doctor.cabinet,
        price_default=float(doctor.price_default) if doctor.price_default else None,
        start_number_online=doctor.start_number_online,
        max_online_per_day=doctor.max_online_per_day,
        auto_close_time=doctor.auto_close_time,
        active=doctor.active,
        created_at=doctor.created_at,
        updated_at=doctor.updated_at,
    )


def service_to_type(service: Service) -> ServiceType:
    """Конвертировать Service в ServiceType"""
    return ServiceType(
        id=service.id,
        name=service.name,
        code=service.code,
        price=float(service.price),
        category=service.category,
        description=service.description,
        duration_minutes=service.duration_minutes,
        doctor=doctor_to_type(service.doctor) if service.doctor else None,
        active=service.active,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


def appointment_to_type(appointment: Appointment) -> AppointmentType:
    """Конвертировать Appointment в AppointmentType"""
    return AppointmentType(
        id=appointment.id,
        patient=patient_to_type(appointment.patient),
        doctor=doctor_to_type(appointment.doctor),
        service=service_to_type(appointment.service),
        appointment_date=appointment.appointment_date,
        status=appointment.status,
        notes=appointment.notes,
        payment_status=appointment.payment_status,
        payment_amount=(
            float(appointment.payment_amount) if appointment.payment_amount else None
        ),
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


def visit_to_type(visit: Visit) -> VisitType:
    """Конвертировать Visit в VisitType"""
    return VisitType(
        id=visit.id,
        patient=patient_to_type(visit.patient),
        doctor=doctor_to_type(visit.doctor),
        visit_date=visit.visit_date,
        visit_time=visit.visit_time,
        status=visit.status,
        discount_mode=visit.discount_mode,
        all_free=visit.all_free,
        total_amount=float(visit.total_amount) if visit.total_amount else None,
        payment_status=visit.payment_status,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
    )


def queue_entry_to_type(entry: OnlineQueueEntry) -> QueueEntryType:
    """Конвертировать OnlineQueueEntry в QueueEntryType"""
    return QueueEntryType(
        id=entry.id,
        patient=patient_to_type(entry.patient),
        doctor=doctor_to_type(entry.doctor),
        queue_number=entry.queue_number,
        status=entry.status,
        created_at=entry.created_at,
        called_at=entry.called_at,
        completed_at=entry.completed_at,
    )


def daily_queue_to_type(queue: DailyQueue) -> DailyQueueType:
    """Конвертировать DailyQueue в DailyQueueType"""
    return DailyQueueType(
        id=queue.id,
        doctor=doctor_to_type(queue.doctor),
        queue_date=queue.queue_date,
        queue_tag=queue.queue_tag,
        current_number=queue.current_number,
        last_called_number=queue.last_called_number,
        is_active=queue.is_active,
        cabinet_number=queue.cabinet_number,
        cabinet_floor=queue.cabinet_floor,
        cabinet_building=queue.cabinet_building,
        created_at=queue.created_at,
        updated_at=queue.updated_at,
    )


# ===================== QUERY RESOLVERS =====================


@strawberry.type
class Query:
    """GraphQL Query"""

    # ===================== PATIENTS =====================

    @strawberry.field
    def patients(
        self,
        filter: Optional[PatientFilter] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PaginatedPatients:
        """Получить список пациентов"""
        db = get_db_session()

        query = db.query(Patient)

        # Применяем фильтры
        if filter:
            if filter.full_name:
                query = query.filter(Patient.full_name.ilike(f"%{filter.full_name}%"))
            if filter.phone:
                query = query.filter(Patient.phone.ilike(f"%{filter.phone}%"))
            if filter.email:
                query = query.filter(Patient.email.ilike(f"%{filter.email}%"))
            if filter.created_after:
                query = query.filter(Patient.created_at >= filter.created_after)
            if filter.created_before:
                query = query.filter(Patient.created_at <= filter.created_before)

        # Подсчитываем общее количество
        total = query.count()

        # Применяем пагинацию
        if pagination:
            query = apply_pagination(query, pagination.page, pagination.per_page)
            page = pagination.page
            per_page = pagination.per_page
        else:
            page = 1
            per_page = 20

        patients = query.all()

        return PaginatedPatients(
            items=[patient_to_type(p) for p in patients],
            pagination=create_pagination_info(page, per_page, total),
        )

    @strawberry.field
    def patient(self, id: int) -> Optional[PatientType]:
        """Получить пациента по ID"""
        db = get_db_session()
        patient = db.query(Patient).filter(Patient.id == id).first()
        return patient_to_type(patient) if patient else None

    # ===================== DOCTORS =====================

    @strawberry.field
    def doctors(
        self,
        filter: Optional[DoctorFilter] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PaginatedDoctors:
        """Получить список врачей"""
        db = get_db_session()

        query = db.query(Doctor)

        # Применяем фильтры
        if filter:
            if filter.specialty:
                query = query.filter(Doctor.specialty.ilike(f"%{filter.specialty}%"))
            if filter.cabinet:
                query = query.filter(Doctor.cabinet.ilike(f"%{filter.cabinet}%"))
            if filter.active is not None:
                query = query.filter(Doctor.active == filter.active)

        # Подсчитываем общее количество
        total = query.count()

        # Применяем пагинацию
        if pagination:
            query = apply_pagination(query, pagination.page, pagination.per_page)
            page = pagination.page
            per_page = pagination.per_page
        else:
            page = 1
            per_page = 20

        doctors = query.all()

        return PaginatedDoctors(
            items=[doctor_to_type(d) for d in doctors],
            pagination=create_pagination_info(page, per_page, total),
        )

    @strawberry.field
    def doctor(self, id: int) -> Optional[DoctorType]:
        """Получить врача по ID"""
        db = get_db_session()
        doctor = db.query(Doctor).filter(Doctor.id == id).first()
        return doctor_to_type(doctor) if doctor else None

    # ===================== SERVICES =====================

    @strawberry.field
    def services(
        self,
        filter: Optional[ServiceFilter] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PaginatedServices:
        """Получить список услуг"""
        db = get_db_session()

        query = db.query(Service)

        # Применяем фильтры
        if filter:
            if filter.name:
                query = query.filter(Service.name.ilike(f"%{filter.name}%"))
            if filter.code:
                query = query.filter(Service.code.ilike(f"%{filter.code}%"))
            if filter.category:
                query = query.filter(Service.category.ilike(f"%{filter.category}%"))
            if filter.doctor_id:
                query = query.filter(Service.doctor_id == filter.doctor_id)
            if filter.active is not None:
                query = query.filter(Service.active == filter.active)
            if filter.price_min:
                query = query.filter(Service.price >= filter.price_min)
            if filter.price_max:
                query = query.filter(Service.price <= filter.price_max)

        # Подсчитываем общее количество
        total = query.count()

        # Применяем пагинацию
        if pagination:
            query = apply_pagination(query, pagination.page, pagination.per_page)
            page = pagination.page
            per_page = pagination.per_page
        else:
            page = 1
            per_page = 20

        services = query.all()

        return PaginatedServices(
            items=[service_to_type(s) for s in services],
            pagination=create_pagination_info(page, per_page, total),
        )

    @strawberry.field
    def service(self, id: int) -> Optional[ServiceType]:
        """Получить услугу по ID"""
        db = get_db_session()
        service = db.query(Service).filter(Service.id == id).first()
        return service_to_type(service) if service else None

    # ===================== APPOINTMENTS =====================

    @strawberry.field
    def appointments(
        self,
        filter: Optional[AppointmentFilter] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PaginatedAppointments:
        """Получить список записей"""
        db = get_db_session()

        query = db.query(Appointment)

        # Применяем фильтры
        if filter:
            if filter.patient_id:
                query = query.filter(Appointment.patient_id == filter.patient_id)
            if filter.doctor_id:
                query = query.filter(Appointment.doctor_id == filter.doctor_id)
            if filter.service_id:
                query = query.filter(Appointment.service_id == filter.service_id)
            if filter.status:
                query = query.filter(Appointment.status == filter.status)
            if filter.payment_status:
                query = query.filter(
                    Appointment.payment_status == filter.payment_status
                )
            if filter.date_from:
                query = query.filter(Appointment.appointment_date >= filter.date_from)
            if filter.date_to:
                query = query.filter(Appointment.appointment_date <= filter.date_to)

        # Подсчитываем общее количество
        total = query.count()

        # Применяем пагинацию
        if pagination:
            query = apply_pagination(query, pagination.page, pagination.per_page)
            page = pagination.page
            per_page = pagination.per_page
        else:
            page = 1
            per_page = 20

        appointments = query.all()

        return PaginatedAppointments(
            items=[appointment_to_type(a) for a in appointments],
            pagination=create_pagination_info(page, per_page, total),
        )

    @strawberry.field
    def appointment(self, id: int) -> Optional[AppointmentType]:
        """Получить запись по ID"""
        db = get_db_session()
        appointment = db.query(Appointment).filter(Appointment.id == id).first()
        return appointment_to_type(appointment) if appointment else None

    # ===================== VISITS =====================

    @strawberry.field
    def visits(
        self,
        filter: Optional[VisitFilter] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PaginatedVisits:
        """Получить список визитов"""
        db = get_db_session()

        query = db.query(Visit)

        # Применяем фильтры
        if filter:
            if filter.patient_id:
                query = query.filter(Visit.patient_id == filter.patient_id)
            if filter.doctor_id:
                query = query.filter(Visit.doctor_id == filter.doctor_id)
            if filter.status:
                query = query.filter(Visit.status == filter.status)
            if filter.payment_status:
                query = query.filter(Visit.payment_status == filter.payment_status)
            if filter.date_from:
                query = query.filter(Visit.visit_date >= filter.date_from)
            if filter.date_to:
                query = query.filter(Visit.visit_date <= filter.date_to)
            if filter.discount_mode:
                query = query.filter(Visit.discount_mode == filter.discount_mode)
            if filter.all_free is not None:
                query = query.filter(Visit.all_free == filter.all_free)

        # Подсчитываем общее количество
        total = query.count()

        # Применяем пагинацию
        if pagination:
            query = apply_pagination(query, pagination.page, pagination.per_page)
            page = pagination.page
            per_page = pagination.per_page
        else:
            page = 1
            per_page = 20

        visits = query.all()

        return PaginatedVisits(
            items=[visit_to_type(v) for v in visits],
            pagination=create_pagination_info(page, per_page, total),
        )

    @strawberry.field
    def visit(self, id: int) -> Optional[VisitType]:
        """Получить визит по ID"""
        db = get_db_session()
        visit = db.query(Visit).filter(Visit.id == id).first()
        return visit_to_type(visit) if visit else None

    # ===================== QUEUES =====================

    @strawberry.field
    def queue_entries(
        self,
        filter: Optional[QueueFilter] = None,
        pagination: Optional[PaginationInput] = None,
    ) -> PaginatedQueueEntries:
        """Получить список записей в очереди"""
        db = get_db_session()

        query = db.query(OnlineQueueEntry)

        # Применяем фильтры
        if filter:
            if filter.doctor_id:
                query = query.filter(OnlineQueueEntry.doctor_id == filter.doctor_id)
            if filter.queue_date:
                query = query.filter(
                    func.date(OnlineQueueEntry.created_at) == filter.queue_date
                )
            if filter.status:
                query = query.filter(OnlineQueueEntry.status == filter.status)

        # Подсчитываем общее количество
        total = query.count()

        # Применяем пагинацию
        if pagination:
            query = apply_pagination(query, pagination.page, pagination.per_page)
            page = pagination.page
            per_page = pagination.per_page
        else:
            page = 1
            per_page = 20

        entries = query.all()

        return PaginatedQueueEntries(
            items=[queue_entry_to_type(e) for e in entries],
            pagination=create_pagination_info(page, per_page, total),
        )

    # ===================== STATISTICS =====================

    @strawberry.field
    def appointment_stats(self) -> AppointmentStats:
        """Получить статистику записей"""
        db = get_db_session()

        total = db.query(Appointment).count()
        today = (
            db.query(Appointment)
            .filter(func.date(Appointment.appointment_date) == date.today())
            .count()
        )

        # Здесь можно добавить больше статистики
        return AppointmentStats(
            total=total,
            today=today,
            this_week=0,  # TODO: реализовать
            this_month=0,  # TODO: реализовать
            by_status=[],  # TODO: реализовать
            by_payment_status=[],  # TODO: реализовать
        )

    @strawberry.field
    def visit_stats(self) -> VisitStats:
        """Получить статистику визитов"""
        db = get_db_session()

        total = db.query(Visit).count()
        today = db.query(Visit).filter(Visit.visit_date == date.today()).count()

        return VisitStats(
            total=total,
            today=today,
            this_week=0,  # TODO: реализовать
            this_month=0,  # TODO: реализовать
            by_status=[],  # TODO: реализовать
            by_discount_mode=[],  # TODO: реализовать
            total_revenue=0.0,  # TODO: реализовать
        )

    @strawberry.field
    def queue_stats(self) -> QueueStats:
        """Получить статистику очередей"""
        db = get_db_session()

        total_entries = db.query(OnlineQueueEntry).count()
        active_queues = (
            db.query(DailyQueue).filter(DailyQueue.is_active == True).count()
        )

        return QueueStats(
            total_entries=total_entries,
            active_queues=active_queues,
            average_wait_time=0.0,  # TODO: реализовать
            completed_today=0,  # TODO: реализовать
            pending_today=0,  # TODO: реализовать
        )

    @strawberry.field
    def doctor_stats(self, doctor_id: int) -> Optional[DoctorStats]:
        """Получить статистику врача"""
        db = get_db_session()

        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
        if not doctor:
            return None

        total_appointments = (
            db.query(Appointment).filter(Appointment.doctor_id == doctor_id).count()
        )
        total_visits = db.query(Visit).filter(Visit.doctor_id == doctor_id).count()

        return DoctorStats(
            total_appointments=total_appointments,
            total_visits=total_visits,
            today_appointments=0,  # TODO: реализовать
            today_visits=0,  # TODO: реализовать
            average_rating=None,  # TODO: реализовать
            total_revenue=0.0,  # TODO: реализовать
        )

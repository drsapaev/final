"""
GraphQL резолверы для API клиники

GQL-AUDIT-28 follow-up:
- P0-1: сессия берётся как ``with get_db_session() as db:`` (ранее
  ``db = get_db_session()`` без ``with`` ломал все резолверы в рантайме).
- Типы и запросы выровнены с реальными моделями SQLAlchemy (day/specialist,
  number, doc_type/doc_number и т.д. — см. types.py).
"""

from datetime import date

import strawberry
from sqlalchemy import or_

from app.core.specialties import specialty_variants
from app.graphql.types import (
    AppointmentFilter,
    AppointmentStats,
    AppointmentType,
    DailyQueueType,
    DoctorFilter,
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
    PatientType,
    QueueEntryType,
    QueueFilter,
    QueueStats,
    ServiceFilter,
    ServiceType,
    UserType,
    VisitFilter,
    VisitStats,
    VisitType,
)
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit
from app.services.patient_access_audit import log_patient_access_many


def get_db_session():
    """Получить сессию базы данных.

    GQL-AUDIT-28 P0-1: ранее next(get_db()) потреблял генератор, но
    finally: db.close() никогда не выполнялся → утечка сессий БД.
    Возвращает context manager для использования как 'with get_db_session() as db:'.
    """
    from contextlib import contextmanager

    from app.db.session import SessionLocal

    @contextmanager
    def _session():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    return _session()


# ===================== UTILITY FUNCTIONS =====================

# Codex P1 (round-6): server-side pagination bounds, comparable to the REST
# patient endpoints (limit: Query(100, ge=1, le=500..1000)). GraphQL is an
# admin PHI surface in the same threat model: per_page=0 used to divide by
# zero in create_pagination_info, and an unbounded per_page materialized the
# whole table (one PHI audit write per row).
PAGINATION_MAX_PER_PAGE = 1000


def _bounded_pagination(pagination: PaginationInput | None) -> tuple[int, int]:
    """Clamp caller-supplied page/per_page to server-side bounds.

    page < 1 -> 1; per_page < 1 -> 1; per_page > PAGINATION_MAX_PER_PAGE ->
    PAGINATION_MAX_PER_PAGE. The SDL contract (nullable int defaults) is
    unchanged — clamping happens where the values are consumed.
    """
    page = pagination.page if pagination else 1
    per_page = pagination.per_page if pagination else 20
    page = max(1, page)
    per_page = max(1, min(per_page, PAGINATION_MAX_PER_PAGE))
    return page, per_page


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


def patient_full_name(patient: Patient) -> str:
    """SSOT-совместимое ФИО: Patient хранит last/first/middle раздельно."""
    parts = [patient.last_name, patient.first_name, patient.middle_name]
    return " ".join(p for p in parts if p).strip()


def _audit_patient_access(
    info: strawberry.Info, db, patient_ids: list[int], resource_type: str
) -> None:
    """M4-P0-1: каждый доступ admin-актора к PHI пациентов — в audit log.

    Codex round-7 P2: батч-вариант — один COMMIT на список (раньше
    log_patient_access коммитил на subject: perPage=1000 давал до 1000
    последовательных транзакций + expire_on_commit reloads).
    Non-blocking; пропускается, когда контекста нет (прямые тесты схемы).
    """
    user = getattr(info.context, "user", None) if info.context else None
    if not user:
        return
    log_patient_access_many(
        db,
        actor_user=user,
        subject_patient_ids=patient_ids,
        resource_type=resource_type,
        action="view",
        request=getattr(info.context, "request", None),
    )


# ===================== CONVERTERS =====================


def user_to_type(user) -> UserType:
    """Конвертировать User в UserType"""
    return UserType(
        id=user.id,
        username=user.username,
        full_name=user.full_name,
        email=user.email,
        role=user.role,
        is_active=user.is_active,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def patient_to_type(patient: Patient) -> PatientType:
    """Конвертировать Patient в PatientType"""
    return PatientType(
        id=patient.id,
        full_name=patient_full_name(patient),
        phone=patient.phone,
        email=patient.email,
        sex=patient.sex,
        birth_date=patient.birth_date,
        address=patient.address,
        doc_type=patient.doc_type,
        doc_number=patient.doc_number,
        created_at=patient.created_at,
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
        price=float(service.price) if service.price is not None else None,
        unit=service.unit,
        currency=service.currency,
        category_code=service.category_code,
        active=service.active,
        created_at=service.created_at,
        updated_at=service.updated_at,
    )


def appointment_to_type(appointment: Appointment) -> AppointmentType:
    """Конвертировать Appointment в AppointmentType"""
    return AppointmentType(
        id=appointment.id,
        patient=(patient_to_type(appointment.patient) if appointment.patient else None),
        doctor=doctor_to_type(appointment.doctor) if appointment.doctor else None,
        appointment_date=appointment.appointment_date,
        appointment_time=appointment.appointment_time,
        status=appointment.status,
        notes=appointment.notes,
        services=appointment.services,
        payment_type=appointment.payment_type,
        payment_amount=(
            float(appointment.payment_amount)
            if appointment.payment_amount is not None
            else None
        ),
        created_at=appointment.created_at,
        updated_at=appointment.updated_at,
    )


def visit_to_type(visit: Visit) -> VisitType:
    """Конвертировать Visit в VisitType"""
    return VisitType(
        id=visit.id,
        patient=patient_to_type(visit.patient) if visit.patient else None,
        doctor=doctor_to_type(visit.doctor) if visit.doctor else None,
        visit_date=visit.visit_date,
        visit_time=visit.visit_time,
        status=visit.status,
        discount_mode=visit.discount_mode,
        notes=visit.notes,
        created_at=visit.created_at,
        updated_at=visit.updated_at,
    )


def daily_queue_to_type(queue: DailyQueue) -> DailyQueueType:
    """Конвертировать DailyQueue в DailyQueueType"""
    return DailyQueueType(
        id=queue.id,
        specialist=doctor_to_type(queue.specialist) if queue.specialist else None,
        day=queue.day,
        queue_tag=queue.queue_tag,
        active=queue.active,
        opened_at=queue.opened_at,
        cabinet_number=queue.cabinet_number,
        cabinet_floor=queue.cabinet_floor,
        cabinet_building=queue.cabinet_building,
        created_at=queue.created_at,
    )


def queue_entry_to_type(entry: OnlineQueueEntry) -> QueueEntryType:
    """Конвертировать OnlineQueueEntry в QueueEntryType"""
    return QueueEntryType(
        id=entry.id,
        queue=daily_queue_to_type(entry.queue) if entry.queue else None,
        patient=patient_to_type(entry.patient) if entry.patient else None,
        number=entry.number,
        status=entry.status,
        source=entry.source,
        queue_time=entry.queue_time,
        called_at=entry.called_at,
        created_at=entry.created_at,
    )


# ===================== QUERY RESOLVERS =====================


@strawberry.type
class Query:
    """GraphQL Query"""

    # ===================== PATIENTS =====================

    @strawberry.field
    def patients(
        self,
        info: strawberry.Info,
        filter: PatientFilter | None = None,
        pagination: PaginationInput | None = None,
    ) -> PaginatedPatients:
        """Получить список пациентов"""
        with get_db_session() as db:
            query = db.query(Patient).filter(Patient.is_deleted.is_(False))

            # Применяем фильтры
            if filter:
                if filter.full_name:
                    # ФИО хранится раздельно — ищем по всем трём частям
                    like = f"%{filter.full_name}%"
                    query = query.filter(
                        or_(
                            Patient.last_name.ilike(like),
                            Patient.first_name.ilike(like),
                            Patient.middle_name.ilike(like),
                        )
                    )
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

            # Применяем пагинацию (дефолт LIMIT 20; page>=1, 1<=per_page<=1000 —
            # не материализуем таблицу)
            page, per_page = _bounded_pagination(pagination)
            query = apply_pagination(query, page, per_page)

            patients = query.all()
            _audit_patient_access(info, db, [p.id for p in patients], "patient")

            return PaginatedPatients(
                items=[patient_to_type(p) for p in patients],
                pagination=create_pagination_info(page, per_page, total),
            )

    @strawberry.field
    def patient(self, info: strawberry.Info, id: int) -> PatientType | None:
        """Получить пациента по ID"""
        with get_db_session() as db:
            patient = (
                db.query(Patient)
                .filter(Patient.id == id, Patient.is_deleted.is_(False))
                .first()
            )
            if patient:
                _audit_patient_access(info, db, [patient.id], "patient")
            return patient_to_type(patient) if patient else None

    # ===================== DOCTORS =====================

    @strawberry.field
    def doctors(
        self,
        filter: DoctorFilter | None = None,
        pagination: PaginationInput | None = None,
    ) -> PaginatedDoctors:
        """Получить список врачей"""
        with get_db_session() as db:
            query = db.query(Doctor)

            # Применяем фильтры
            if filter:
                if filter.specialty:
                    # D-1 canonical vocabulary (Codex round-8 P2): every
                    # dental-family spelling matches — a legacy 'stomatology'
                    # / 'dental' GraphQL filter keeps finding canonical
                    # 'dentistry' rows after 0049.
                    query = query.filter(
                        or_(
                            *[
                                Doctor.specialty.ilike(f"%{variant}%")
                                for variant in specialty_variants(filter.specialty)
                            ]
                        )
                    )
                if filter.cabinet:
                    query = query.filter(Doctor.cabinet.ilike(f"%{filter.cabinet}%"))
                if filter.active is not None:
                    query = query.filter(Doctor.active == filter.active)

            # Подсчитываем общее количество
            total = query.count()

            # Применяем пагинацию (дефолт LIMIT 20; page>=1, 1<=per_page<=1000 —
            # не материализуем таблицу)
            page, per_page = _bounded_pagination(pagination)
            query = apply_pagination(query, page, per_page)

            doctors = query.all()

            return PaginatedDoctors(
                items=[doctor_to_type(d) for d in doctors],
                pagination=create_pagination_info(page, per_page, total),
            )

    @strawberry.field
    def doctor(self, id: int) -> DoctorType | None:
        """Получить врача по ID"""
        with get_db_session() as db:
            doctor = db.query(Doctor).filter(Doctor.id == id).first()
            return doctor_to_type(doctor) if doctor else None

    # ===================== SERVICES =====================

    @strawberry.field
    def services(
        self,
        filter: ServiceFilter | None = None,
        pagination: PaginationInput | None = None,
    ) -> PaginatedServices:
        """Получить список услуг"""
        with get_db_session() as db:
            query = db.query(Service)

            # Применяем фильтры
            if filter:
                if filter.name:
                    query = query.filter(Service.name.ilike(f"%{filter.name}%"))
                if filter.code:
                    query = query.filter(Service.code.ilike(f"%{filter.code}%"))
                if filter.category_code:
                    query = query.filter(
                        Service.category_code.ilike(f"%{filter.category_code}%")
                    )
                if filter.active is not None:
                    query = query.filter(Service.active == filter.active)
                if filter.price_min is not None:
                    query = query.filter(Service.price >= filter.price_min)
                if filter.price_max is not None:
                    query = query.filter(Service.price <= filter.price_max)

            # Подсчитываем общее количество
            total = query.count()

            # Применяем пагинацию (дефолт LIMIT 20; page>=1, 1<=per_page<=1000 —
            # не материализуем таблицу)
            page, per_page = _bounded_pagination(pagination)
            query = apply_pagination(query, page, per_page)

            services = query.all()

            return PaginatedServices(
                items=[service_to_type(s) for s in services],
                pagination=create_pagination_info(page, per_page, total),
            )

    @strawberry.field
    def service(self, id: int) -> ServiceType | None:
        """Получить услугу по ID"""
        with get_db_session() as db:
            service = db.query(Service).filter(Service.id == id).first()
            return service_to_type(service) if service else None

    # ===================== APPOINTMENTS =====================

    @strawberry.field
    def appointments(
        self,
        info: strawberry.Info,
        filter: AppointmentFilter | None = None,
        pagination: PaginationInput | None = None,
    ) -> PaginatedAppointments:
        """Получить список записей"""
        with get_db_session() as db:
            query = db.query(Appointment)

            # Применяем фильтры
            if filter:
                if filter.patient_id:
                    query = query.filter(Appointment.patient_id == filter.patient_id)
                if filter.doctor_id:
                    query = query.filter(Appointment.doctor_id == filter.doctor_id)
                if filter.status:
                    query = query.filter(Appointment.status == filter.status)
                if filter.payment_type:
                    query = query.filter(
                        Appointment.payment_type == filter.payment_type
                    )
                if filter.date_from:
                    query = query.filter(
                        Appointment.appointment_date >= filter.date_from
                    )
                if filter.date_to:
                    query = query.filter(Appointment.appointment_date <= filter.date_to)

            # Подсчитываем общее количество
            total = query.count()

            # Применяем пагинацию (дефолт LIMIT 20; page>=1, 1<=per_page<=1000 —
            # не материализуем таблицу)
            page, per_page = _bounded_pagination(pagination)
            query = apply_pagination(query, page, per_page)

            appointments = query.all()
            _audit_patient_access(
                info,
                db,
                [a.patient_id for a in appointments if a.patient_id],
                "appointment",
            )

            return PaginatedAppointments(
                items=[appointment_to_type(a) for a in appointments],
                pagination=create_pagination_info(page, per_page, total),
            )

    @strawberry.field
    def appointment(self, info: strawberry.Info, id: int) -> AppointmentType | None:
        """Получить запись по ID"""
        with get_db_session() as db:
            appointment = db.query(Appointment).filter(Appointment.id == id).first()
            if appointment and appointment.patient_id:
                _audit_patient_access(info, db, [appointment.patient_id], "appointment")
            return appointment_to_type(appointment) if appointment else None

    # ===================== VISITS =====================

    @strawberry.field
    def visits(
        self,
        info: strawberry.Info,
        filter: VisitFilter | None = None,
        pagination: PaginationInput | None = None,
    ) -> PaginatedVisits:
        """Получить список визитов"""
        with get_db_session() as db:
            query = db.query(Visit)

            # Применяем фильтры
            if filter:
                if filter.patient_id:
                    query = query.filter(Visit.patient_id == filter.patient_id)
                if filter.doctor_id:
                    query = query.filter(Visit.doctor_id == filter.doctor_id)
                if filter.status:
                    query = query.filter(Visit.status == filter.status)
                if filter.date_from:
                    query = query.filter(Visit.visit_date >= filter.date_from)
                if filter.date_to:
                    query = query.filter(Visit.visit_date <= filter.date_to)
                if filter.discount_mode:
                    query = query.filter(Visit.discount_mode == filter.discount_mode)

            # Подсчитываем общее количество
            total = query.count()

            # Применяем пагинацию (дефолт LIMIT 20; page>=1, 1<=per_page<=1000 —
            # не материализуем таблицу)
            page, per_page = _bounded_pagination(pagination)
            query = apply_pagination(query, page, per_page)

            visits = query.all()
            _audit_patient_access(
                info, db, [v.patient_id for v in visits if v.patient_id], "visit"
            )

            return PaginatedVisits(
                items=[visit_to_type(v) for v in visits],
                pagination=create_pagination_info(page, per_page, total),
            )

    @strawberry.field
    def visit(self, info: strawberry.Info, id: int) -> VisitType | None:
        """Получить визит по ID"""
        with get_db_session() as db:
            visit = db.query(Visit).filter(Visit.id == id).first()
            if visit and visit.patient_id:
                _audit_patient_access(info, db, [visit.patient_id], "visit")
            return visit_to_type(visit) if visit else None

    # ===================== QUEUES =====================

    @strawberry.field
    def queue_entries(
        self,
        info: strawberry.Info,
        filter: QueueFilter | None = None,
        pagination: PaginationInput | None = None,
    ) -> PaginatedQueueEntries:
        """Получить список записей в очереди"""
        with get_db_session() as db:
            # OnlineQueueEntry не имеет doctor_id/даты — фильтруем через очередь
            query = db.query(OnlineQueueEntry).join(
                DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id
            )

            # Применяем фильтры
            if filter:
                if filter.doctor_id:
                    query = query.filter(DailyQueue.specialist_id == filter.doctor_id)
                if filter.queue_date:
                    query = query.filter(DailyQueue.day == filter.queue_date)
                if filter.queue_tag:
                    query = query.filter(DailyQueue.queue_tag == filter.queue_tag)
                if filter.status:
                    query = query.filter(OnlineQueueEntry.status == filter.status)

            # Подсчитываем общее количество
            total = query.count()

            # Применяем пагинацию (дефолт LIMIT 20; page>=1, 1<=per_page<=1000 —
            # не материализуем таблицу)
            page, per_page = _bounded_pagination(pagination)
            query = apply_pagination(query, page, per_page)

            entries = query.all()
            _audit_patient_access(
                info,
                db,
                [e.patient_id for e in entries if e.patient_id],
                "cabinet_summary",
            )

            return PaginatedQueueEntries(
                items=[queue_entry_to_type(e) for e in entries],
                pagination=create_pagination_info(page, per_page, total),
            )

    # ===================== STATISTICS =====================

    @strawberry.field
    def appointment_stats(self) -> AppointmentStats:
        """Получить статистику записей"""
        with get_db_session() as db:
            total = db.query(Appointment).count()
            today = (
                db.query(Appointment)
                .filter(Appointment.appointment_date == date.today())
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
        with get_db_session() as db:
            total = db.query(Visit).count()
            today = db.query(Visit).filter(Visit.visit_date == date.today()).count()

            return VisitStats(
                total=total,
                today=today,
                this_week=0,  # TODO: реализовать
                this_month=0,  # TODO: реализовать
                by_status=[],  # TODO: реализовать
                by_discount_mode=[],  # TODO: реализовать
                total_revenue=0.0,  # TODO: суммы в VisitService/invoices
            )

    @strawberry.field
    def queue_stats(self) -> QueueStats:
        """Получить статистику очередей"""
        with get_db_session() as db:
            total_entries = db.query(OnlineQueueEntry).count()
            active_queues = (
                db.query(DailyQueue).filter(DailyQueue.active == True).count()
            )  # noqa: E712

            return QueueStats(
                total_entries=total_entries,
                active_queues=active_queues,
                average_wait_time=0.0,  # TODO: реализовать
                completed_today=0,  # TODO: реализовать
                pending_today=0,  # TODO: реализовать
            )

    @strawberry.field
    def doctor_stats(self, doctor_id: int) -> DoctorStats | None:
        """Получить статистику врача"""
        with get_db_session() as db:
            doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()
            if not doctor:
                return None

            total_appointments = (
                db.query(Appointment).filter(Appointment.doctor_id == doctor_id).count()
            )
            total_visits = db.query(Visit).filter(Visit.doctor_id == doctor_id).count()
            today_appointments = (
                db.query(Appointment)
                .filter(
                    Appointment.doctor_id == doctor_id,
                    Appointment.appointment_date == date.today(),
                )
                .count()
            )
            today_visits = (
                db.query(Visit)
                .filter(
                    Visit.doctor_id == doctor_id,
                    Visit.visit_date == date.today(),
                )
                .count()
            )

            return DoctorStats(
                total_appointments=total_appointments,
                total_visits=total_visits,
                today_appointments=today_appointments,
                today_visits=today_visits,
                average_rating=None,  # TODO: реализовать
                total_revenue=0.0,  # TODO: суммы в invoices
            )

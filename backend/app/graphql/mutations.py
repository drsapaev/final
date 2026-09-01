"""
GraphQL мутации для API клиники

GQL-AUDIT-28 follow-up:
- P0-1: сессия берётся как ``with get_db_session() as db:`` (ранее
  ``db = get_db_session()`` без ``with`` ломал все мутации в рантайме,
  а try/except превращал AttributeError в тихий INTERNAL_ERROR).
- Логика выровнена с реальными моделями и CRUD-SSOT (soft delete,
  create_appointment, create_visit, get_or_create_daily_queue).
"""

from datetime import UTC, date, datetime
from zoneinfo import ZoneInfo

import strawberry
from fastapi import HTTPException
from sqlalchemy import func

from app.core.i18n import t
from app.crud import (
    online_queue as crud_queue,
)

# NOTE: ``from app.crud import patient/appointment`` возвращает ИНСТАНСЫ
# CRUD-классов (star-import в app/crud/__init__.py), поэтому module-level
# SSOT-функции импортируем напрямую из модулей crud.
from app.crud.appointment import (
    appointment as appointment_crud,  # instance: update_status / cancel_appointment
)
from app.crud.appointment import (
    create_appointment as crud_create_appointment,
)
from app.crud.clinic import get_queue_settings
from app.crud.patient import (
    patient as patient_crud,  # instance: get_patient_by_phone
)
from app.crud.patient import (
    soft_delete_patient,
    update_patient,
)
from app.crud.visit import create_visit
from app.graphql.resolvers import (
    appointment_to_type,
    get_db_session,
    patient_to_type,
    queue_entry_to_type,
    service_to_type,
    visit_to_type,
)
from app.graphql.types import (
    AppointmentInput,
    AppointmentMutationResponse,
    MutationResponse,
    PatientInput,
    PatientMutationResponse,
    PatientUpdateInput,
    QueueEntryInput,
    QueueMutationResponse,
    ServiceInput,
    ServiceMutationResponse,
    VisitInput,
    VisitMutationResponse,
)
from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.enums import AppointmentStatus, VisitStatus
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit


def _patient_update_data(input: PatientUpdateInput) -> dict:
    """Собрать dict обновления только из переданных полей."""
    update_data = {}
    if input.last_name is not None:
        update_data["last_name"] = input.last_name
    if input.first_name is not None:
        update_data["first_name"] = input.first_name
    if input.middle_name is not None:
        update_data["middle_name"] = input.middle_name
    if input.phone is not None:
        update_data["phone"] = input.phone
    if input.email is not None:
        update_data["email"] = input.email
    if input.birth_date is not None:
        update_data["birth_date"] = input.birth_date
    if input.sex is not None:
        update_data["sex"] = input.sex
    if input.address is not None:
        update_data["address"] = input.address
    if input.doc_type is not None:
        update_data["doc_type"] = input.doc_type
    if input.doc_number is not None:
        update_data["doc_number"] = input.doc_number
    return update_data


@strawberry.type
class Mutation:
    """GraphQL Mutations"""

    # ===================== PATIENT MUTATIONS =====================

    @strawberry.mutation
    def create_patient(self, input: PatientInput) -> PatientMutationResponse:
        """Создать нового пациента"""
        try:
            with get_db_session() as db:
                # Проверяем, не существует ли пациент с таким телефоном
                if input.phone:
                    existing = patient_crud.get_patient_by_phone(db, phone=input.phone)
                    if existing and not existing.is_deleted:
                        return PatientMutationResponse(
                            success=False,
                            message="Пациент с таким номером телефона уже существует",
                            errors=["PHONE_EXISTS"],
                        )

                # Создаем нового пациента (имена хранятся раздельно)
                patient = Patient(
                    last_name=input.last_name,
                    first_name=input.first_name,
                    middle_name=input.middle_name,
                    phone=input.phone,
                    email=input.email,
                    birth_date=input.birth_date,
                    sex=input.sex,
                    address=input.address,
                    doc_type=input.doc_type,
                    doc_number=input.doc_number,
                )
                db.add(patient)
                db.commit()
                db.refresh(patient)

                return PatientMutationResponse(
                    success=True,
                    message="Пациент успешно создан",
                    patient=patient_to_type(patient),
                )

        except Exception:
            return PatientMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def update_patient(
        self, id: int, input: PatientUpdateInput
    ) -> PatientMutationResponse:
        """Обновить данные пациента"""
        try:
            with get_db_session() as db:
                patient = (
                    db.query(Patient)
                    .filter(Patient.id == id, Patient.is_deleted.is_(False))
                    .first()
                )
                if not patient:
                    return PatientMutationResponse(
                        success=False,
                        message=t("patient.not_found"),
                        errors=["PATIENT_NOT_FOUND"],
                    )

                # Обновляем только переданные поля (SSOT: mobile API wrapper)
                update_data = _patient_update_data(input)
                updated_patient = update_patient(
                    db, patient_id=id, update_data=update_data
                )

                return PatientMutationResponse(
                    success=True,
                    message="Пациент успешно обновлен",
                    patient=patient_to_type(updated_patient),
                )

        except Exception:
            return PatientMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def delete_patient(self, info: strawberry.Info, id: int) -> MutationResponse:
        """Удалить пациента"""
        try:
            with get_db_session() as db:
                patient = (
                    db.query(Patient)
                    .filter(Patient.id == id, Patient.is_deleted.is_(False))
                    .first()
                )
                if not patient:
                    return MutationResponse(
                        success=False,
                        message=t("patient.not_found"),
                        errors=["PATIENT_NOT_FOUND"],
                    )

                # Проверяем, есть ли связанные записи
                appointments_count = (
                    db.query(Appointment).filter(Appointment.patient_id == id).count()
                )
                visits_count = db.query(Visit).filter(Visit.patient_id == id).count()

                if appointments_count > 0 or visits_count > 0:
                    return MutationResponse(
                        success=False,
                        message="Нельзя удалить пациента с существующими записями или визитами",
                        errors=["HAS_RELATED_RECORDS"],
                    )

                # SSOT: soft delete; deleted_by — РЕАЛЬНЫЙ user.id
                # (FK users.id; user приходит из контекста роутера, None —
                # только в прямых тестах схемы без контекста)
                actor = getattr(info.context, "user", None) if info.context else None
                soft_delete_patient(
                    db, patient_id=id, deleted_by=actor.id if actor else None
                )

                return MutationResponse(success=True, message="Пациент успешно удален")

        except Exception:
            return MutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    # ===================== APPOINTMENT MUTATIONS =====================

    @strawberry.mutation
    def create_appointment(
        self, input: AppointmentInput
    ) -> AppointmentMutationResponse:
        """Создать новую запись"""
        try:
            with get_db_session() as db:
                # Проверяем существование пациента и врача
                patient = (
                    db.query(Patient)
                    .filter(
                        Patient.id == input.patient_id,
                        Patient.is_deleted.is_(False),
                    )
                    .first()
                )
                if not patient:
                    return AppointmentMutationResponse(
                        success=False,
                        message=t("patient.not_found"),
                        errors=["PATIENT_NOT_FOUND"],
                    )

                doctor = None
                if input.doctor_id:
                    doctor = (
                        db.query(Doctor).filter(Doctor.id == input.doctor_id).first()
                    )
                    if not doctor:
                        return AppointmentMutationResponse(
                            success=False,
                            message=t("doctor.not_found"),
                            errors=["DOCTOR_NOT_FOUND"],
                        )

                # Создаем запись (SSOT: crud create_appointment)
                appointment = crud_create_appointment(
                    db,
                    {
                        "patient_id": input.patient_id,
                        "doctor_id": input.doctor_id,
                        "appointment_date": input.appointment_date,
                        "appointment_time": input.appointment_time,
                        "notes": input.notes,
                        "services": input.services,
                        "status": AppointmentStatus.PENDING.value,
                        "payment_type": None,
                        "payment_amount": None,
                    },
                )

                return AppointmentMutationResponse(
                    success=True,
                    message="Запись успешно создана",
                    appointment=appointment_to_type(appointment),
                )

        except Exception:
            return AppointmentMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def update_appointment_status(
        self, id: int, status: str
    ) -> AppointmentMutationResponse:
        """Обновить статус записи"""
        try:
            with get_db_session() as db:
                # SSOT: канонические статусы AppointmentStatus (enum)
                valid_statuses = [s.value for s in AppointmentStatus]
                if status not in valid_statuses:
                    return AppointmentMutationResponse(
                        success=False,
                        message=f"Недопустимый статус. Допустимые: {', '.join(valid_statuses)}",
                        errors=["INVALID_STATUS"],
                    )

                # SSOT: CRUD-метод; state machine ВКЛЮЧЕНА — терминальные
                # статусы нельзя переоткрыть (completed -> pending и т.п.)
                try:
                    updated = appointment_crud.update_status(
                        db,
                        appointment_id=id,
                        new_status=status,
                        validate_transition=True,
                    )
                except HTTPException as exc:
                    return AppointmentMutationResponse(
                        success=False,
                        message=str(exc.detail),
                        errors=["INVALID_STATUS_TRANSITION"],
                    )
                if not updated:
                    return AppointmentMutationResponse(
                        success=False,
                        message=t("error.not_found"),
                        errors=["APPOINTMENT_NOT_FOUND"],
                    )

                return AppointmentMutationResponse(
                    success=True,
                    message="Статус записи успешно обновлен",
                    appointment=appointment_to_type(updated),
                )

        except Exception:
            return AppointmentMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def cancel_appointment(
        self, id: int, reason: str | None = None
    ) -> AppointmentMutationResponse:
        """Отменить запись"""
        try:
            with get_db_session() as db:
                appointment = db.query(Appointment).filter(Appointment.id == id).first()
                if not appointment:
                    return AppointmentMutationResponse(
                        success=False,
                        message=t("error.not_found"),
                        errors=["APPOINTMENT_NOT_FOUND"],
                    )

                if appointment.status == "completed":
                    return AppointmentMutationResponse(
                        success=False,
                        message="Нельзя отменить завершенную запись",
                        errors=["CANNOT_CANCEL_COMPLETED"],
                    )

                # SSOT: CRUD-метод отмены (валидированный переход статуса)
                updated = appointment_crud.cancel_appointment(db, appointment_id=id)
                if reason:
                    updated.notes = (updated.notes or "") + f"\nОтменено: {reason}"
                    db.commit()
                    db.refresh(updated)

                return AppointmentMutationResponse(
                    success=True,
                    message="Запись успешно отменена",
                    appointment=appointment_to_type(updated),
                )

        except Exception:
            return AppointmentMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    # ===================== VISIT MUTATIONS =====================

    @strawberry.mutation
    def create_visit(self, input: VisitInput) -> VisitMutationResponse:
        """Создать новый визит"""
        try:
            with get_db_session() as db:
                # Проверяем существование пациента и врача
                patient = (
                    db.query(Patient)
                    .filter(
                        Patient.id == input.patient_id,
                        Patient.is_deleted.is_(False),
                    )
                    .first()
                )
                if not patient:
                    return VisitMutationResponse(
                        success=False,
                        message=t("patient.not_found"),
                        errors=["PATIENT_NOT_FOUND"],
                    )

                doctor = None
                if input.doctor_id:
                    doctor = (
                        db.query(Doctor).filter(Doctor.id == input.doctor_id).first()
                    )
                    if not doctor:
                        return VisitMutationResponse(
                            success=False,
                            message=t("doctor.not_found"),
                            errors=["DOCTOR_NOT_FOUND"],
                        )

                # Проверяем услуги
                services = []
                if input.service_ids:
                    services = (
                        db.query(Service)
                        .filter(Service.id.in_(input.service_ids))
                        .all()
                    )
                    if len(services) != len(input.service_ids):
                        return VisitMutationResponse(
                            success=False,
                            message="Одна или несколько услуг не найдены",
                            errors=["SERVICES_NOT_FOUND"],
                        )

                # Подготавливаем услуги для SSOT create_visit.
                # Цены — КАНОНИЧЕСКИЕ (service.price); расчёт скидок
                # (repeat/benefit/all_free) остаётся SSOT биллинга
                # (DiscountBenefitsService) — дублировать проценты здесь
                # нельзя. discount_mode сохраняется на визите как факт.
                services_data = []
                for service in services:
                    services_data.append(
                        {
                            "service_id": service.id,
                            "code": service.code,
                            "name": service.name,
                            "qty": 1,
                            "price": float(service.price or 0),
                        }
                    )

                # SSOT: единая функция create_visit
                visit = create_visit(
                    db=db,
                    patient_id=input.patient_id,
                    doctor_id=input.doctor_id,
                    visit_date=input.visit_date,
                    visit_time=input.visit_time,
                    discount_mode=input.discount_mode or "none",
                    notes=input.notes,
                    services=services_data,
                    status="scheduled",
                    auto_status=False,  # Статус уже установлен
                    notify=False,
                    log=True,
                )

                return VisitMutationResponse(
                    success=True,
                    message="Визит успешно создан",
                    visit=visit_to_type(visit),
                )

        except Exception:
            return VisitMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def update_visit_status(self, id: int, status: str) -> VisitMutationResponse:
        """Обновить статус визита"""
        try:
            with get_db_session() as db:
                visit = db.query(Visit).filter(Visit.id == id).first()
                if not visit:
                    return VisitMutationResponse(
                        success=False,
                        message=t("visit.not_found"),
                        errors=["VISIT_NOT_FOUND"],
                    )

                # SSOT: канонические статусы VisitStatus (enum)
                valid_statuses = [s.value for s in VisitStatus]
                if status not in valid_statuses:
                    return VisitMutationResponse(
                        success=False,
                        message=f"Недопустимый статус. Допустимые: {', '.join(valid_statuses)}",
                        errors=["INVALID_STATUS"],
                    )

                visit.status = status
                visit.updated_at = datetime.now(UTC)
                db.commit()
                db.refresh(visit)

                return VisitMutationResponse(
                    success=True,
                    message="Статус визита успешно обновлен",
                    visit=visit_to_type(visit),
                )

        except Exception:
            return VisitMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    # ===================== SERVICE MUTATIONS =====================

    @strawberry.mutation
    def create_service(self, input: ServiceInput) -> ServiceMutationResponse:
        """Создать новую услугу"""
        try:
            with get_db_session() as db:
                # Проверяем уникальность кода
                if input.code:
                    existing = (
                        db.query(Service).filter(Service.code == input.code).first()
                    )
                    if existing:
                        return ServiceMutationResponse(
                            success=False,
                            message="Услуга с таким кодом уже существует",
                            errors=["CODE_EXISTS"],
                        )

                # Создаем услугу
                service = Service(
                    name=input.name,
                    code=input.code,
                    price=input.price,
                    unit=input.unit,
                    currency=input.currency,
                    category_code=input.category_code,
                    active=True,
                )
                db.add(service)
                db.commit()
                db.refresh(service)

                return ServiceMutationResponse(
                    success=True,
                    message="Услуга успешно создана",
                    service=service_to_type(service),
                )

        except Exception:
            return ServiceMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def update_service_price(self, id: int, price: float) -> ServiceMutationResponse:
        """Обновить цену услуги"""
        try:
            with get_db_session() as db:
                service = db.query(Service).filter(Service.id == id).first()
                if not service:
                    return ServiceMutationResponse(
                        success=False,
                        message="Услуга не найдена",
                        errors=["SERVICE_NOT_FOUND"],
                    )

                if price < 0:
                    return ServiceMutationResponse(
                        success=False,
                        message="Цена не может быть отрицательной",
                        errors=["INVALID_PRICE"],
                    )

                service.price = price
                service.updated_at = datetime.now(UTC)
                db.commit()
                db.refresh(service)

                return ServiceMutationResponse(
                    success=True,
                    message="Цена услуги успешно обновлена",
                    service=service_to_type(service),
                )

        except Exception:
            return ServiceMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    # ===================== QUEUE MUTATIONS =====================

    @strawberry.mutation
    def join_queue(self, input: QueueEntryInput) -> QueueMutationResponse:
        """Встать в очередь"""
        try:
            with get_db_session() as db:
                # Проверяем существование пациента и врача
                patient = (
                    db.query(Patient)
                    .filter(
                        Patient.id == input.patient_id,
                        Patient.is_deleted.is_(False),
                    )
                    .first()
                )
                if not patient:
                    return QueueMutationResponse(
                        success=False,
                        message=t("patient.not_found"),
                        errors=["PATIENT_NOT_FOUND"],
                    )

                doctor = db.query(Doctor).filter(Doctor.id == input.doctor_id).first()
                if not doctor:
                    return QueueMutationResponse(
                        success=False,
                        message=t("doctor.not_found"),
                        errors=["DOCTOR_NOT_FOUND"],
                    )

                today = date.today()
                # SSOT: get_or_create_daily_queue (уникальность day+specialist+tag)
                daily_queue = crud_queue.get_or_create_daily_queue(
                    db,
                    day=today,
                    specialist_id=input.doctor_id,
                    queue_tag=input.queue_tag,
                )

                # Правила онлайн-набора — как в SSOT join_online_queue:
                # приём открыт (opened_at) -> онлайн-запись закрыта
                if daily_queue.opened_at:
                    return QueueMutationResponse(
                        success=False,
                        message="Онлайн-набор закрыт. Обратитесь в регистратуру.",
                        errors=["QUEUE_CLOSED"],
                    )

                # рабочие часы (настройки клиники, timezone-aware)
                queue_settings = get_queue_settings(db)
                timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
                queue_start_hour = queue_settings.get("queue_start_hour", 7)
                if datetime.now(timezone).hour < queue_start_hour:
                    return QueueMutationResponse(
                        success=False,
                        message=f"Онлайн-запись доступна с {queue_start_hour}:00",
                        errors=["OUTSIDE_HOURS"],
                    )

                # Проверяем, не стоит ли пациент уже в очереди к этому врачу сегодня
                existing_entry = (
                    db.query(OnlineQueueEntry)
                    .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                    .filter(
                        OnlineQueueEntry.patient_id == input.patient_id,
                        DailyQueue.specialist_id == input.doctor_id,
                        DailyQueue.day == today,
                        OnlineQueueEntry.status.in_(["waiting", "called"]),
                    )
                    .first()
                )

                if existing_entry:
                    return QueueMutationResponse(
                        success=False,
                        message="Пациент уже стоит в очереди к этому врачу сегодня",
                        errors=["ALREADY_IN_QUEUE"],
                    )

                # GQL-AUDIT-28 P0-3 (codex r2): лочим строку очереди ДО
                # вычисления MAX(number) — иначе параллельные joinQueue
                # читают одинаковый MAX и вставляют дубликаты номеров
                daily_queue = (
                    db.query(DailyQueue)
                    .filter(DailyQueue.id == daily_queue.id)
                    .with_for_update()
                    .first()
                )

                # Лимит: индивидуальный на очередь -> капа врача
                online_entries_count = (
                    db.query(OnlineQueueEntry)
                    .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                    .filter(
                        DailyQueue.specialist_id == input.doctor_id,
                        DailyQueue.day == today,
                    )
                    .count()
                )

                max_slots = (
                    daily_queue.max_online_entries
                    if daily_queue.max_online_entries is not None
                    else doctor.max_online_per_day
                )
                if online_entries_count >= max_slots:
                    return QueueMutationResponse(
                        success=False,
                        message="Превышен лимит онлайн записей на сегодня",
                        errors=["QUEUE_LIMIT_EXCEEDED"],
                    )

                # GQL-AUDIT-28 P0-3: race на выдаче номера — берём MAX(number)
                # внутри транзакции; у DailyQueue нет счётчика current_number
                next_number = (
                    db.query(func.max(OnlineQueueEntry.number))
                    .filter(OnlineQueueEntry.queue_id == daily_queue.id)
                    .scalar()
                    or 0
                ) + 1

                queue_entry = OnlineQueueEntry(
                    queue_id=daily_queue.id,
                    number=next_number,
                    patient_id=input.patient_id,
                    status="waiting",
                    source="online",
                    queue_time=datetime.now(UTC),
                )

                db.add(queue_entry)
                db.commit()
                db.refresh(queue_entry)

                return QueueMutationResponse(
                    success=True,
                    message=f"Вы встали в очередь под номером {next_number}",
                    queue_entry=queue_entry_to_type(queue_entry),
                )

        except Exception:
            return QueueMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def call_next_patient(
        self, doctor_id: int, queue_tag: str | None = None
    ) -> QueueMutationResponse:
        """Вызвать следующего пациента"""
        try:
            with get_db_session() as db:
                # Находим следующего пациента в очереди (через дневную очередь)
                query = (
                    db.query(OnlineQueueEntry)
                    .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                    .filter(
                        DailyQueue.specialist_id == doctor_id,
                        DailyQueue.day == date.today(),
                        OnlineQueueEntry.status == "waiting",
                    )
                )

                if queue_tag:
                    query = query.filter(DailyQueue.queue_tag == queue_tag)

                # GQL-AUDIT-28 P0-2: with_for_update — защита от race condition
                next_entry = (
                    query.order_by(OnlineQueueEntry.number).with_for_update().first()
                )

                if not next_entry:
                    return QueueMutationResponse(
                        success=False,
                        message="Нет пациентов в очереди",
                        errors=["NO_PATIENTS_IN_QUEUE"],
                    )

                # Обновляем статус и время вызова
                next_entry.status = "called"
                next_entry.called_at = datetime.now(UTC)

                db.commit()
                db.refresh(next_entry)

                return QueueMutationResponse(
                    success=True,
                    message=f"Вызван пациент под номером {next_entry.number}",
                    queue_entry=queue_entry_to_type(next_entry),
                )

        except Exception:
            return QueueMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

"""
GraphQL мутации для API клиники

GQL-AUDIT-28 follow-up:
- P0-1: сессия берётся как ``with get_db_session() as db:`` (ранее
  ``db = get_db_session()`` без ``with`` ломал все мутации в рантайме,
  а try/except превращал AttributeError в тихий INTERNAL_ERROR).
- Логика выровнена с реальными моделями и CRUD-SSOT (soft delete,
  create_appointment, create_visit, get_or_create_daily_queue).
"""

import logging
from datetime import UTC, date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

import strawberry
from fastapi import HTTPException
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import func, text
from strawberry import UNSET

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
from app.crud.patient import soft_delete_patient
from app.crud.visit import create_visit
from app.schemas.patient import PatientCreate, PatientUpdate
from app.services.appointment_eligibility import (
    ensure_doctor_eligible_for_appointment,
)
from app.services.appointment_slot_guard import lock_doctor_for_slot_reservation
from app.services.display_websocket import get_display_manager
from app.services.patient_service import PatientService
from app.services.qr_queue import QRQueueService
from app.services.queue_position_notifications import get_queue_position_service
from app.services.services_api_service import ServicesApiService
from app.services.visit_lifecycle_service import VisitLifecycleService

logger = logging.getLogger(__name__)
from app.graphql.resolvers import (
    _audit_patient_access,
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
from app.models.enums import AppointmentStatus
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit


@strawberry.type
class Mutation:
    """GraphQL Mutations"""

    # ===================== PATIENT MUTATIONS =====================

    @strawberry.mutation
    def create_patient(
        self, info: strawberry.Info, input: PatientInput
    ) -> PatientMutationResponse:
        """Создать нового пациента (SSOT: PatientService.create_patient)."""
        actor = getattr(info.context, "user", None) if info.context else None
        if not actor:
            return PatientMutationResponse(
                success=False,
                message=t("error.unauthorized"),
                errors=["UNAUTHENTICATED"],
            )
        try:
            with get_db_session() as db:
                # SSOT: валидация/санитизация, дубликаты телефона и документа,
                # аудит критичных изменений, уведомление о регистрации —
                # всё в каноническом сервисе (AGENTS.md L155-158).
                patient_in = PatientCreate(
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
                patient = PatientService(db).create_patient(
                    request=getattr(info.context, "request", None),
                    patient_in=patient_in,
                    current_user=actor,
                )

                # M4-P0-1: ответ мутации отдаёт PHI пациента — пишем read-trail
                _audit_patient_access(info, db, [patient.id], "patient")

                return PatientMutationResponse(
                    success=True,
                    message="Пациент успешно создан",
                    patient=patient_to_type(patient),
                )

        except HTTPException as exc:
            detail = str(exc.detail)
            if "номером телефона" in detail:
                return PatientMutationResponse(
                    success=False, message=detail, errors=["PHONE_EXISTS"]
                )
            if "документа" in detail:
                return PatientMutationResponse(
                    success=False, message=detail, errors=["DOC_NUMBER_EXISTS"]
                )
            return PatientMutationResponse(
                success=False, message=detail, errors=["VALIDATION_ERROR"]
            )
        except Exception:
            return PatientMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

    @strawberry.mutation
    def update_patient(
        self, info: strawberry.Info, id: int, input: PatientUpdateInput
    ) -> PatientMutationResponse:
        """Обновить пациента (SSOT: PatientService.update_patient)."""
        actor = getattr(info.context, "user", None) if info.context else None
        if not actor:
            return PatientMutationResponse(
                success=False,
                message=t("error.unauthorized"),
                errors=["UNAUTHENTICATED"],
            )
        try:
            with get_db_session() as db:
                # Codex P1: в PatientUpdateInput попадают ТОЛЬКО реально
                # переданные поля (опущенные = UNSET). Раньше все поля
                # уходили в PatientUpdate как None, и CRUDBase.update
                # (model_dump(exclude_unset=True)) затирал ими телефон,
                # email, документ и т.д. при частичном обновлении.
                update_fields = {}
                for field_name in (
                    "last_name",
                    "first_name",
                    "middle_name",
                    "phone",
                    "email",
                    "birth_date",
                    "sex",
                    "address",
                    "doc_type",
                    "doc_number",
                ):
                    value = getattr(input, field_name)
                    if value is not UNSET:
                        update_fields[field_name] = value

                # SSOT: duplicate-phone check, critical-change audit и т.д.
                updated_patient = PatientService(db).update_patient(
                    request=getattr(info.context, "request", None),
                    patient_id=id,
                    patient_in=PatientUpdate(**update_fields),
                    current_user=actor,
                )

                # M4-P0-1: ответ мутации отдаёт PHI пациента — пишем read-trail
                _audit_patient_access(info, db, [updated_patient.id], "patient")

                return PatientMutationResponse(
                    success=True,
                    message="Пациент успешно обновлен",
                    patient=patient_to_type(updated_patient),
                )

        except HTTPException as exc:
            detail = str(exc.detail)
            if "не найден" in detail or "not found" in detail.lower():
                return PatientMutationResponse(
                    success=False, message=detail, errors=["PATIENT_NOT_FOUND"]
                )
            if "номером телефона" in detail:
                return PatientMutationResponse(
                    success=False, message=detail, errors=["PHONE_EXISTS"]
                )
            return PatientMutationResponse(
                success=False, message=detail, errors=["VALIDATION_ERROR"]
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
        self, info: strawberry.Info, input: AppointmentInput
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

                    # SSOT: атомарная бронь слота (как в canonical endpoint) —
                    # per-doctor FOR UPDATE lock ДО проверки занятости
                    lock_doctor_for_slot_reservation(db, input.doctor_id)
                    ensure_doctor_eligible_for_appointment(db, input.doctor_id)
                    if input.appointment_time and (
                        appointment_crud.is_time_slot_occupied(
                            db,
                            doctor_id=input.doctor_id,
                            appointment_date=input.appointment_date,
                            appointment_time=input.appointment_time,
                        )
                    ):
                        return AppointmentMutationResponse(
                            success=False,
                            message="Это время уже занято у выбранного врача",
                            errors=["SLOT_OCCUPIED"],
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

                # M4-P0-1: appointment_to_type включает patient (PHI) — read-trail
                if appointment.patient_id:
                    _audit_patient_access(
                        info, db, [appointment.patient_id], "appointment"
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
        self, info: strawberry.Info, id: int, status: str
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

                # M4-P0-1: ответ включает patient (PHI) — read-trail
                if updated.patient_id:
                    _audit_patient_access(info, db, [updated.patient_id], "appointment")

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
        self, info: strawberry.Info, id: int, reason: str | None = None
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

                # M4-P0-1: ответ включает patient (PHI) — read-trail
                if updated.patient_id:
                    _audit_patient_access(info, db, [updated.patient_id], "appointment")

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
    def create_visit(
        self, info: strawberry.Info, input: VisitInput
    ) -> VisitMutationResponse:
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
                # Codex P1: цены считаются КАНОНИЧЕСКИМ прайсингом регистратуры
                # (_apply_service_discount из registrar_wizard/_helpers — тот же
                # путь, что в /registrar/cart) ДО персистенса, а не постфактум
                # в биллинге. Иначе VisitService хранит базовую цену и потом
                # нельзя отличить «скидка не применена» от «скидка потеряна».
                # AGENTS.md L155-158: нет второго источника прайсинга.
                from app.api.v1.endpoints.registrar_wizard._helpers import (
                    _apply_service_discount,
                    _check_repeat_visit_eligibility,
                    _load_registration_discount_settings,
                    _normalize_registration_discount_mode,
                )
                from app.services.service_mapping import get_service_code

                discount_mode = _normalize_registration_discount_mode(
                    input.discount_mode
                )
                registration_settings = _load_registration_discount_settings(db)

                if discount_mode == "repeat":
                    # Канонический guard корзины: повторный визит возможен
                    # только при консультации у этого врача за N дней
                    repeat_days = int(registration_settings["repeat_visit_days"])
                    if not _check_repeat_visit_eligibility(
                        db,
                        input.patient_id,
                        input.doctor_id,
                        [s.id for s in services],
                        days_window=repeat_days,
                    ):
                        return VisitMutationResponse(
                            success=False,
                            message=(
                                "Повторный визит недоступен: нет консультации "
                                f"у этого врача за последние {repeat_days} дней"
                            ),
                            errors=["REPEAT_VISIT_NOT_ELIGIBLE"],
                        )

                services_data = []
                for service in services:
                    base_price = Decimal(str(service.price or 0))
                    item_price = _apply_service_discount(
                        base_price,
                        discount_mode,
                        registration_settings,
                        service.is_consultation,
                    )
                    services_data.append(
                        {
                            "service_id": service.id,
                            # SSOT: canonical service_code helper (как в /registrar/cart)
                            "code": service.service_code
                            or get_service_code(service.id, db),
                            "name": service.name,
                            "qty": 1,
                            "price": float(item_price),
                        }
                    )

                # SSOT: единая функция create_visit
                visit = create_visit(
                    db=db,
                    patient_id=input.patient_id,
                    doctor_id=input.doctor_id,
                    visit_date=input.visit_date,
                    visit_time=input.visit_time,
                    discount_mode=discount_mode,
                    notes=input.notes,
                    services=services_data,
                    # SSOT: канонический стартовый статус жизненного цикта
                    status="pending_confirmation",
                    # Каноническое правило корзины: all_free требует
                    # подтверждения, если не включён all_free_auto_approve
                    approval_status=(
                        "approved"
                        if discount_mode != "all_free"
                        or registration_settings["all_free_auto_approve"]
                        else "pending"
                    ),
                    auto_status=False,
                    notify=False,
                    log=True,
                )

                # M4-P0-1: visit_to_type включает patient (PHI) — read-trail
                if visit.patient_id:
                    _audit_patient_access(info, db, [visit.patient_id], "visit")

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
    def update_visit_status(
        self, info: strawberry.Info, id: int, status: str
    ) -> VisitMutationResponse:
        """Обновить статус визита (SSOT: VisitLifecycleService)."""
        actor = getattr(info.context, "user", None) if info.context else None
        if not actor:
            return VisitMutationResponse(
                success=False,
                message=t("error.unauthorized"),
                errors=["UNAUTHENTICATED"],
            )
        try:
            with get_db_session() as db:
                visit = db.query(Visit).filter(Visit.id == id).first()
                if not visit:
                    return VisitMutationResponse(
                        success=False,
                        message=t("visit.not_found"),
                        errors=["VISIT_NOT_FOUND"],
                    )

                # SSOT: state machine жизненного цикла (терминальные статусы
                # закрыты; timestamps и аудит ведёт канонический сервис)
                updated = VisitLifecycleService(db).transition_status(
                    id, status, actor, commit=True
                )

                # M4-P0-1: ответ включает patient (PHI) — read-trail
                if updated.patient_id:
                    _audit_patient_access(info, db, [updated.patient_id], "visit")

                return VisitMutationResponse(
                    success=True,
                    message="Статус визита успешно обновлен",
                    visit=visit_to_type(updated),
                )

        except HTTPException as exc:
            return VisitMutationResponse(
                success=False,
                message=str(exc.detail),
                errors=["INVALID_STATUS_TRANSITION"],
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
        """Создать новую услугу (SSOT: ServicesApiService.create_service)"""
        try:
            with get_db_session() as db:
                # Codex P1: сырое Service(...) пропускало нормализацию кода,
                # категорию/префикс-валидацию и service-аудит, оставляя
                # service_code пустым — queue-домен не видел такую услугу.
                # Делегируем каноническому сервису REST-эндпоинта услуг.
                try:
                    service = ServicesApiService(db).create_service(
                        service_data={
                            "name": input.name,
                            "code": input.code,
                            "price": input.price,
                            "unit": input.unit,
                            "currency": input.currency,
                            "category_code": input.category_code,
                        }
                    )
                except ValueError as exc:
                    # канонический сервис: дубликат кода
                    return ServiceMutationResponse(
                        success=False,
                        message=str(exc),
                        errors=["CODE_EXISTS"],
                    )
                except HTTPException as exc:
                    # канонический сервис: prefix/payload валидация (422)
                    return ServiceMutationResponse(
                        success=False,
                        message=str(exc.detail),
                        errors=["VALIDATION_ERROR"],
                    )

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

    @staticmethod
    def _join_queue_impl(
        info: strawberry.Info, input: QueueEntryInput
    ) -> QueueMutationResponse:
        """Синхронная транзакция joinQueue (запускается в threadpool)."""
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
                # P1: сериализуем СОЗДАНИЕ очереди на ключе (doctor, day, tag) —
                # get_or_create_daily_queue это query-then-insert без
                # unique-констрейнта; advisory lock (Postgres) закрывает гонку
                # двух первых joinQueue. SQLite (тесты) пропускает.
                if db.bind is not None and db.bind.dialect.name == "postgresql":
                    db.execute(
                        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
                        {
                            "k": (
                                f"daily_queue:{input.doctor_id}:"
                                f"{today.isoformat()}:{input.queue_tag or ''}"
                            )
                        },
                    )

                # SSOT: get_or_create_daily_queue (уникальность day+specialist+tag)
                daily_queue = crud_queue.get_or_create_daily_queue(
                    db,
                    day=today,
                    specialist_id=input.doctor_id,
                    queue_tag=input.queue_tag,
                )

                # P1: лочим строку очереди ДО проверок дубликата/лимита и
                # выдачи номера — параллельные joinQueue выстраиваются здесь
                # и заново проходят проверки после блокировки.
                daily_queue = (
                    db.query(DailyQueue)
                    .filter(DailyQueue.id == daily_queue.id)
                    .with_for_update()
                    .first()
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

                # рабочие часы (настройки клиники, timezone-aware)
                # Лимит: индивидуальный на очередь -> капа врача

                # Дубликат — ПОСЛЕ блокировки очереди: параллельный второй
                # joinQueue дождётся лока и увидит вставленную первым запись.
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

                # Лимит: считаем записи ВЫБРАННОЙ очереди (не всех очередей
                # врача за день) и сравниваем с её же капой
                online_entries_count = (
                    db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.queue_id == daily_queue.id)
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

                # M4-P0-1: queue_entry_to_type включает patient (PHI) — read-trail
                _audit_patient_access(info, db, [input.patient_id], "cabinet_summary")

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
    async def join_queue(
        self, info: strawberry.Info, input: QueueEntryInput
    ) -> QueueMutationResponse:
        """Встать в очередь.

        Codex P2: после успешного (не дубликатного) join выполняются те же
        broadcast-ы, что и в каноническом /queue/join: queue.created на
        TV-табло + entry_added в админский /ws/queue. DB-часть — в
        threadpool (не блокируем event loop), broadcast-ы — после коммита.
        """
        # Strawberry может вызвать корневой резолвер с self=None —
        # вызываем staticmethod по классу, а не по инстансу.
        response = await run_in_threadpool(Mutation._join_queue_impl, info, input)
        if not (response.success and response.queue_entry):
            return response

        entry = response.queue_entry
        specialist_id = (
            entry.queue.specialist.id
            if entry.queue and entry.queue.specialist
            else input.doctor_id
        )
        day = entry.queue.day if entry.queue else date.today()

        # 1) TV-табло: queue.created (payload строится при открытой сессии —
        # entry2.queue/patient lazy-load; после закрытия был бы DetachedInstanceError)
        try:
            manager = get_display_manager()
            with get_db_session() as db2:
                entry2 = (
                    db2.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.id == entry.id)
                    .first()
                )
                if entry2:
                    await manager.broadcast_queue_update(
                        queue_entry=entry2, event_type="queue.created"
                    )
        except Exception as e:  # noqa: BLE001 — non-blocking
            logger.warning("GraphQL joinQueue: display broadcast failed: %s", e)

        # 2) админский WS /ws/queue: entry_added
        try:
            from app.ws.queue_ws import broadcast_queue_update

            broadcast_queue_update(
                department=f"specialist_{specialist_id}",
                date=day.strftime("%Y-%m-%d"),
                event_type="queue_update",
                data={
                    "action": "entry_added",
                    "entry_id": entry.id,
                    "number": entry.number,
                },
            )
        except Exception as e:  # noqa: BLE001 — non-blocking
            logger.warning("GraphQL joinQueue: queue WS broadcast failed: %s", e)

        return response

    @strawberry.mutation
    async def call_next_patient(
        self,
        info: strawberry.Info,
        doctor_id: int,
        queue_tag: str | None = None,
    ) -> QueueMutationResponse:
        """Вызвать следующего пациента (SSOT: QRQueueService.call_next_patient
        + уведомления/бродкасты, как в canonical qr_queue endpoint)."""
        actor = getattr(info.context, "user", None) if info.context else None
        if not actor:
            return QueueMutationResponse(
                success=False,
                message=t("error.unauthorized"),
                errors=["UNAUTHENTICATED"],
            )
        try:
            entry_snapshot = None
            entry_id = None
            cabinet = None
            specialist_name = "Врач"
            with get_db_session() as db:
                # SSOT: with_for_update, called_by-аудит, канонические ответы;
                # queue_tag передаётся в канонический сервис (фильтр очереди).
                result = await run_in_threadpool(
                    QRQueueService(db).call_next_patient,
                    doctor_id,
                    actor.id,
                    None,
                    queue_tag,
                )

                if not result.get("success"):
                    return QueueMutationResponse(
                        success=False,
                        message=result.get("message", "Нет пациентов в очереди"),
                        errors=["NO_PATIENTS_IN_QUEUE"],
                    )

                entry_id = result.get("patient", {}).get("id")
                entry = (
                    db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.id == entry_id)
                    .first()
                    if entry_id
                    else None
                )
                if entry:
                    entry_snapshot = queue_entry_to_type(entry)
                    # M4-P0-1: снапшот включает patient (PHI) — read-trail
                    if entry.patient_id:
                        _audit_patient_access(
                            info, db, [entry.patient_id], "cabinet_summary"
                        )
                    if entry.queue:
                        cabinet = entry.queue.cabinet_number or (
                            entry.queue.specialist.cabinet
                            if entry.queue.specialist
                            else None
                        )

            # --- Side effects (canonical qr_queue endpoint semantics) ---
            if entry_id:
                # 1) push-уведомление пациенту
                try:
                    with get_db_session() as db2:
                        notify_service = get_queue_position_service(db2)
                        entry2 = (
                            db2.query(OnlineQueueEntry)
                            .filter(OnlineQueueEntry.id == entry_id)
                            .first()
                        )
                        if entry2:
                            await notify_service.notify_patient_called(
                                entry2, cabinet_number=cabinet
                            )
                except Exception as e:  # noqa: BLE001 — non-blocking
                    logger.warning(
                        "GraphQL callNext: notify_patient_called failed: %s", e
                    )

                # 2) TV-табло — payload строится и отправляется, ПОКА
                # сессия открыта (entry3.queue/specialist — lazy-load;
                # после закрытия сессии был бы DetachedInstanceError)
                try:
                    manager = get_display_manager()
                    with get_db_session() as db3:
                        entry3 = (
                            db3.query(OnlineQueueEntry)
                            .filter(OnlineQueueEntry.id == entry_id)
                            .first()
                        )
                        if entry3:
                            specialist_name = (
                                entry3.queue.specialist.user.full_name
                                if entry3.queue
                                and entry3.queue.specialist
                                and entry3.queue.specialist.user
                                else "Врач"
                            )
                            await manager.broadcast_patient_call(
                                queue_entry=entry3,
                                doctor_name=specialist_name,
                                cabinet=cabinet,
                            )
                except Exception as e:  # noqa: BLE001 — non-blocking
                    logger.warning("GraphQL callNext: display broadcast failed: %s", e)

                # 3) админский WS /ws/queue
                try:
                    from app.ws.queue_ws import broadcast_queue_update

                    broadcast_queue_update(
                        department=f"specialist_{doctor_id}",
                        date=date.today().strftime("%Y-%m-%d"),
                        event_type="queue_update",
                        data={"action": "call_next", "entry_id": entry_id},
                    )
                except Exception as e:  # noqa: BLE001 — non-blocking
                    logger.warning("GraphQL callNext: queue WS broadcast failed: %s", e)

            return QueueMutationResponse(
                success=True,
                message=(
                    f"Вызван пациент под номером {entry_snapshot.number}"
                    if entry_snapshot
                    else (result.get("message") or "Пациент вызван")
                ),
                queue_entry=entry_snapshot,
            )

        except ValueError as exc:
            return QueueMutationResponse(
                success=False, message=str(exc), errors=["QUEUE_NOT_ACTIVE"]
            )
        except Exception:
            return QueueMutationResponse(
                success=False,
                message=t("error.internal"),
                errors=["INTERNAL_ERROR"],
            )

# app/api/v1/endpoints/appointments.py
import logging
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.crud.appointment import appointment as appointment_crud
from app.models import appointment as appointment_models
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.setting import Setting
from app.models.user import User
from app.schemas import appointment as appointment_schemas
from app.services.online_queue import (
    _broadcast,  # Добавляем _broadcast
    get_or_create_day,
    load_stats,
)
from app.services.service_mapping import get_service_code

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/appointments", tags=["appointments"])
APPOINTMENTS_PUBLIC_ERROR = "Internal server error"
APPOINTMENT_BROAD_ACCESS_ROLES = {"Admin", "Registrar"}
APPOINTMENT_DOCTOR_ROLES = {
    "Doctor",
    "cardio",
    "cardiology",
    "Cardiologist",
    "Cardio",
    "derma",
    "Dermatologist",
    "dentist",
    "Dentist",
}
APPOINTMENT_PATIENT_ROLES = {"Patient"}
APPOINTMENT_PENDING_PAYMENT_ROLES = {"Admin", "Registrar", "Cashier"}
APPOINTMENT_RESTRICTED_UPDATE_FIELDS = {
    "payment_amount",
    "payment_currency",
    "payment_processed_at",
    "payment_provider",
    "payment_transaction_id",
    "payment_type",
    "payment_webhook_id",
    "services",
    "status",
    "visit_type",
}


def _appointments_http_error(exc: Exception, operation: str) -> HTTPException:
    logger.warning(
        "Appointments endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    return HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail=APPOINTMENTS_PUBLIC_ERROR,
    )


def _ensure_appointment_record_access(
    db: Session,
    appointment: Any,
    current_user: User,
) -> None:
    role = getattr(current_user, "role", None)
    if role in APPOINTMENT_BROAD_ACCESS_ROLES or getattr(
        current_user, "is_superuser", False
    ):
        return

    if role in APPOINTMENT_DOCTOR_ROLES:
        doctor = (
            db.query(Doctor)
            .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
            .first()
        )
        if not doctor:
            raise HTTPException(status_code=403, detail="Access denied")
        if appointment.doctor_id == doctor.id:
            return

        assigned_doctor = (
            db.query(Doctor).filter(Doctor.id == appointment.doctor_id).first()
        )
        # Some legacy appointment writers stored User.id in doctor_id. Allow it
        # only when that value does not resolve to another real Doctor row.
        if not assigned_doctor and appointment.doctor_id == current_user.id:
            return
        if assigned_doctor and assigned_doctor.user_id == current_user.id:
            return

        raise HTTPException(status_code=403, detail="Access denied")

    if role in APPOINTMENT_PATIENT_ROLES:
        patient_id = getattr(appointment, "patient_id", None)
        if patient_id is None:
            raise HTTPException(status_code=403, detail="Access denied")

        current_patient = getattr(current_user, "patient", None)
        if getattr(current_patient, "id", None) == patient_id:
            return

        patient = (
            db.query(Patient)
            .filter(Patient.id == patient_id, Patient.user_id == current_user.id)
            .first()
        )
        if patient:
            return

    raise HTTPException(status_code=403, detail="Access denied")


def _appointment_doctor_scope_ids(db: Session, current_user: User) -> set[int]:
    doctor = (
        db.query(Doctor)
        .filter(Doctor.user_id == current_user.id, Doctor.active.is_(True))
        .first()
    )
    if not doctor:
        raise HTTPException(status_code=403, detail="Access denied")

    allowed_ids = {doctor.id}
    assigned_doctor = db.query(Doctor).filter(Doctor.id == current_user.id).first()
    if not assigned_doctor:
        allowed_ids.add(current_user.id)
    return allowed_ids


def _appointment_patient_scope_id(db: Session, current_user: User) -> int:
    current_patient = getattr(current_user, "patient", None)
    if getattr(current_patient, "id", None) is not None:
        return current_patient.id

    patient = db.query(Patient).filter(Patient.user_id == current_user.id).first()
    if not patient:
        raise HTTPException(status_code=403, detail="Access denied")
    return patient.id


def _scope_appointment_list_filters(
    db: Session,
    *,
    patient_id: int | None,
    doctor_id: int | None,
    current_user: User,
) -> tuple[int | None, int | None]:
    role = getattr(current_user, "role", None)
    if role in APPOINTMENT_BROAD_ACCESS_ROLES or getattr(
        current_user, "is_superuser", False
    ):
        return patient_id, doctor_id

    if role in APPOINTMENT_DOCTOR_ROLES:
        if doctor_id is None:
            raise HTTPException(status_code=403, detail="Access denied")
        if doctor_id not in _appointment_doctor_scope_ids(db, current_user):
            raise HTTPException(status_code=403, detail="Access denied")
        return patient_id, doctor_id

    if role in APPOINTMENT_PATIENT_ROLES:
        own_patient_id = _appointment_patient_scope_id(db, current_user)
        if patient_id is not None and patient_id != own_patient_id:
            raise HTTPException(status_code=403, detail="Access denied")
        return own_patient_id, doctor_id

    raise HTTPException(status_code=403, detail="Access denied")


def _ensure_appointment_create_access(
    db: Session,
    appointment_in: appointment_schemas.AppointmentCreate,
    current_user: User,
) -> None:
    role = getattr(current_user, "role", None)
    if role in APPOINTMENT_BROAD_ACCESS_ROLES or getattr(
        current_user, "is_superuser", False
    ):
        return

    if role in APPOINTMENT_DOCTOR_ROLES:
        if appointment_in.doctor_id not in _appointment_doctor_scope_ids(
            db, current_user
        ):
            raise HTTPException(status_code=403, detail="Access denied")
        return

    if role in APPOINTMENT_PATIENT_ROLES:
        if appointment_in.patient_id != _appointment_patient_scope_id(
            db, current_user
        ):
            raise HTTPException(status_code=403, detail="Access denied")
        return

    raise HTTPException(status_code=403, detail="Access denied")


def _ensure_pending_payment_access(current_user: User) -> None:
    if getattr(current_user, "role", None) in APPOINTMENT_PENDING_PAYMENT_ROLES:
        return
    if getattr(current_user, "is_superuser", False):
        return
    raise HTTPException(status_code=403, detail="Access denied")


def _ensure_appointment_update_fields_allowed(
    appointment_in: appointment_schemas.AppointmentUpdate,
    current_user: User,
) -> None:
    role = getattr(current_user, "role", None)
    if role in APPOINTMENT_BROAD_ACCESS_ROLES or getattr(
        current_user, "is_superuser", False
    ):
        return

    update_fields = appointment_in.model_dump(exclude_unset=True).keys()
    if APPOINTMENT_RESTRICTED_UPDATE_FIELDS.intersection(update_fields):
        raise HTTPException(status_code=403, detail="Access denied")


# Схема для ответа pending-payments
class PendingPaymentResponse(BaseModel):
    id: int
    patient_id: int | None
    patient_name: str | None
    patient_last_name: str | None
    patient_first_name: str | None
    doctor_id: int | None
    department: str | None
    appointment_date: str | None
    appointment_time: str | None
    status: str
    services: list[str]
    services_names: list[str]
    payment_amount: float | None
    created_at: str | None
    record_type: str
    visit_ids: list[int] | None = None


# --- helpers ---------------------------------------------------------------


def _pick_date(date_str: str | None, date: str | None, d: str | None) -> str:
    """Берём дату из любого из 3х синонимов; если ничего нет — 422."""
    v = date_str or date or d
    if not v:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="date is required (use ?date_str=YYYY-MM-DD or ?date=... or ?d=...)",
        )
    return v


def _upsert_queue_setting(db: Session, key: str, value: str) -> None:
    """Простой upsert в таблицу settings (category='queue'). Гарантируем created_at/updated_at."""
    now = datetime.utcnow()
    row = (
        db.query(Setting)
        .filter(Setting.category == "queue", Setting.key == key)
        .with_for_update(read=True)
        .first()
    )
    if row:
        row.value = value
        row.updated_at = now
    else:
        row = Setting(
            category="queue", key=key, value=value, created_at=now, updated_at=now
        )
        db.add(row)
    # коммит делать в вызывающей функции (у нас — сразу после двух апдейтов)


# --- endpoints -------------------------------------------------------------


@router.get("/", response_model=list[appointment_schemas.Appointment])
def list_appointments(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = Query(None, description="Фильтр по ID пациента"),
    doctor_id: int | None = Query(None, description="Фильтр по ID врача"),
    department: str | None = Query(None, description="Фильтр по отделению"),
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить список записей на прием с возможностью фильтрации и пагинации
    """
    from app.models.patient import Patient

    patient_id, doctor_id = _scope_appointment_list_filters(
        db,
        patient_id=patient_id,
        doctor_id=doctor_id,
        current_user=current_user,
    )

    appointments = appointment_crud.get_appointments(
        db,
        skip=skip,
        limit=limit,
        patient_id=patient_id,
        doctor_id=doctor_id,
        department=department,
        date_from=date_from,
        date_to=date_to,
    )

    # Обогащаем данные именами пациентов и полными наименованиями услуг
    from app.models.service import Service

    result = []
    for apt in appointments:
        # Получаем имя пациента
        patient_name = None
        if apt.patient_id:
            patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
            if patient:
                patient_name = patient.short_name()
            else:
                patient_name = f"Пациент #{apt.patient_id}"

        # Получаем полные наименования услуг
        services_with_names = []
        if apt.services and isinstance(apt.services, list):
            for service_item in apt.services:
                if isinstance(service_item, str):
                    # Если это код услуги (строка)
                    service = (
                        db.query(Service)
                        .filter(
                            (Service.code == service_item)
                            | (Service.service_code == service_item)
                        )
                        .first()
                    )
                    if service:
                        services_with_names.append(service.name)
                    else:
                        services_with_names.append(service_item)  # Fallback на код
                elif isinstance(service_item, dict):
                    # Если это объект с данными услуги
                    if 'name' in service_item:
                        services_with_names.append(service_item['name'])
                    elif 'code' in service_item:
                        service = (
                            db.query(Service)
                            .filter(
                                (Service.code == service_item['code'])
                                | (Service.service_code == service_item['code'])
                            )
                            .first()
                        )
                        if service:
                            services_with_names.append(service.name)
                        else:
                            services_with_names.append(
                                service_item.get('code', 'Услуга')
                            )
                    else:
                        services_with_names.append(str(service_item))
                else:
                    services_with_names.append(str(service_item))

        # Создаем Pydantic модель из SQLAlchemy объекта
        apt_schema = appointment_schemas.Appointment.model_validate(apt)
        # Добавляем patient_name и обновленные services через model_dump
        apt_dict = apt_schema.model_dump()
        apt_dict['patient_name'] = patient_name
        if services_with_names:
            apt_dict['services'] = (
                services_with_names  # Заменяем коды на полные наименования
            )

        result.append(apt_dict)

    return result


@router.post("/", response_model=appointment_schemas.Appointment)
def create_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_in: appointment_schemas.AppointmentCreate,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Создать новую запись на прием
    """
    # Проверяем, не занято ли время у врача
    _ensure_appointment_create_access(db, appointment_in, current_user)

    if appointment_crud.is_time_slot_occupied(
        db,
        doctor_id=appointment_in.doctor_id,
        appointment_date=appointment_in.appointment_date,
        appointment_time=appointment_in.appointment_time,
    ):
        raise HTTPException(
            status_code=400, detail="Это время уже занято у выбранного врача"
        )

    appointment = appointment_crud.create(db=db, obj_in=appointment_in)
    return appointment


@router.get("/pending-payments", include_in_schema=False)
async def get_pending_payments(
    db: Session = Depends(deps.get_db),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    date_from: str | None = Query(default=None),
    date_to: str | None = Query(default=None),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить объединенный список записей (appointments и visits), ожидающие оплаты
    Группирует visits одного пациента в одну запись
    """
    _ensure_pending_payment_access(current_user)

    try:
        from collections import defaultdict

        from app.models.patient import Patient
        from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
        from app.models.service import Service
        from app.models.visit import Visit, VisitService

        result = []

        # 1. Получаем appointments со статусом pending или без оплаты
        appointments_query = db.query(appointment_models.Appointment).filter(
            appointment_models.Appointment.status.in_(
                ["scheduled", "confirmed", "pending"]
            )
        )

        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    appointment_models.Appointment.appointment_date >= from_date
                )
            except ValueError:
                pass

        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                appointments_query = appointments_query.filter(
                    appointment_models.Appointment.appointment_date <= to_date
                )
            except ValueError:
                pass

        appointments = appointments_query.order_by(
            appointment_models.Appointment.created_at.desc()
        ).all()

        # Обрабатываем appointments
        for apt in appointments:
            # Проверяем, не оплачен ли уже
            if apt.payment_amount and apt.status == "paid":
                continue

            # Получаем имя пациента
            patient_name = None
            patient_last_name = None
            patient_first_name = None
            if apt.patient_id:
                patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
                if patient:
                    patient_name = patient.short_name()
                    patient_last_name = patient.last_name
                    patient_first_name = patient.first_name
                else:
                    patient_name = f"Пациент #{apt.patient_id}"

            # Получаем коды услуг и полные наименования
            services_codes = []
            services_names = []
            if apt.services and isinstance(apt.services, list):
                for service_code in apt.services:
                    services_codes.append(service_code)
                    service = (
                        db.query(Service).filter(Service.code == service_code).first()
                    )
                    if service:
                        services_names.append(service.name)
                    else:
                        services_names.append(service_code)

            result.append(
                {
                    'id': apt.id,
                    'patient_id': apt.patient_id,
                    'patient_name': patient_name,
                    'patient_last_name': patient_last_name,
                    'patient_first_name': patient_first_name,
                    'doctor_id': apt.doctor_id,
                    'department': apt.department,
                    'appointment_date': (
                        apt.appointment_date.isoformat()
                        if apt.appointment_date
                        else None
                    ),
                    'appointment_time': apt.appointment_time,
                    'status': apt.status,
                    'services': services_codes,
                    'services_names': services_names,
                    'payment_amount': (
                        float(apt.payment_amount) if apt.payment_amount else None
                    ),
                    'created_at': (
                        apt.created_at.isoformat() if apt.created_at else None
                    ),
                    'record_type': 'appointment',
                    'visit_ids': [],
                }
            )

        # 2. Получаем visits без оплаты
        visits_query = db.query(Visit).filter(
            Visit.status.in_(["pending", "confirmed", "scheduled"])
        )

        if date_from:
            try:
                from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date >= from_date)
            except ValueError:
                pass

        if date_to:
            try:
                to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                visits_query = visits_query.filter(Visit.visit_date <= to_date)
            except ValueError:
                pass

        visits = visits_query.order_by(Visit.created_at.desc()).all()

        # Группируем visits по patient_id и дате
        visits_by_patient = defaultdict(
            lambda: {
                'patient_id': None,
                'patient_name': None,
                'patient_last_name': None,
                'patient_first_name': None,
                'doctor_id': None,
                'department': None,
                'appointment_date': None,
                'appointment_time': None,
                'status': 'pending',
                'services': [],
                'services_names': [],
                'payment_amount': None,
                'created_at': None,
                'record_type': 'visit',
                'visit_ids': [],
            }
        )

        for visit in visits:
            # Проверяем, не оплачен ли уже через PaymentInvoice
            paid_invoices = (
                db.query(PaymentInvoiceVisit)
                .join(PaymentInvoice)
                .filter(
                    PaymentInvoiceVisit.visit_id == visit.id,
                    PaymentInvoice.status == "paid",
                )
                .first()
            )

            if paid_invoices:
                continue  # Уже оплачен

            # Группируем по patient_id и дате (visit_date или created_at.date())
            visit_date = visit.visit_date
            if not visit_date and visit.created_at:
                visit_date = visit.created_at.date()

            # Ключ для группировки: patient_id + дата
            group_key = (
                visit.patient_id,
                visit_date.isoformat() if visit_date else None,
            )

            if group_key not in visits_by_patient:
                # Получаем имя пациента
                patient_name = None
                patient_last_name = None
                patient_first_name = None
                if visit.patient_id:
                    patient = (
                        db.query(Patient).filter(Patient.id == visit.patient_id).first()
                    )
                    if patient:
                        patient_name = patient.short_name()
                        patient_last_name = patient.last_name
                        patient_first_name = patient.first_name

                visits_by_patient[group_key] = {
                    'patient_id': visit.patient_id,
                    'patient_name': patient_name,
                    'patient_last_name': patient_last_name,
                    'patient_first_name': patient_first_name,
                    'doctor_id': visit.doctor_id,
                    'department': visit.department,
                    'appointment_date': visit_date.isoformat() if visit_date else None,
                    'appointment_time': (
                        visit.visit_time.strftime('%H:%M')
                        if visit.visit_time and hasattr(visit.visit_time, 'strftime')
                        else (visit.visit_time if visit.visit_time else None)
                    ),
                    'status': visit.status,
                    'services': [],
                    'services_names': [],
                    'payment_amount': None,
                    'created_at': (
                        visit.created_at.isoformat() if visit.created_at else None
                    ),
                    'record_type': 'visit',
                    'visit_ids': [],
                }

            # Добавляем услуги визита
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            for vs in visit_services:
                if vs.code and vs.code not in visits_by_patient[group_key]['services']:
                    visits_by_patient[group_key]['services'].append(vs.code)
                    visits_by_patient[group_key]['services_names'].append(vs.name)

            visits_by_patient[group_key]['visit_ids'].append(visit.id)

        # Добавляем сгруппированные visits в результат
        for group_data in visits_by_patient.values():
            result.append(group_data)

        # Применяем пагинацию
        total = len(result)  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
        result = result[skip : skip + limit]

        return result

    except Exception as e:
        raise _appointments_http_error(e, "list_appointments") from e


@router.put("/{appointment_id}", response_model=appointment_schemas.Appointment)
def update_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    appointment_in: appointment_schemas.AppointmentUpdate,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Обновить запись на прием
    """
    appointment = appointment_crud.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Проверяем, не занято ли новое время у врача
    _ensure_appointment_record_access(db, appointment, current_user)
    _ensure_appointment_update_fields_allowed(appointment_in, current_user)

    if (
        appointment_in.appointment_date
        or appointment_in.appointment_time
        or appointment_in.doctor_id
    ):
        new_date = appointment_in.appointment_date or appointment.appointment_date
        new_time = appointment_in.appointment_time or appointment.appointment_time
        new_doctor_id = appointment_in.doctor_id or appointment.doctor_id

        if appointment_crud.is_time_slot_occupied(
            db,
            doctor_id=new_doctor_id,
            appointment_date=new_date,
            appointment_time=new_time,
            exclude_appointment_id=appointment_id,
        ):
            raise HTTPException(
                status_code=400, detail="Это время уже занято у выбранного врача"
            )

    appointment = appointment_crud.update(
        db=db, db_obj=appointment, obj_in=appointment_in
    )
    return appointment


@router.delete("/{appointment_id}")
def delete_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Отменить запись на прием
    """
    appointment = appointment_crud.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    _ensure_appointment_record_access(db, appointment, current_user)

    appointment_crud.remove(db=db, id=appointment_id)
    return {"message": "Запись успешно отменена"}


@router.get("/doctor/{doctor_id}/schedule")
def get_doctor_schedule(
    *,
    db: Session = Depends(deps.get_db),
    doctor_id: int,
    date: str = Query(..., description="Дата (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить расписание врача на определенную дату
    """
    schedule = appointment_crud.get_doctor_schedule(db, doctor_id=doctor_id, date=date)
    return schedule


@router.get("/department/{department}/schedule")
def get_department_schedule(
    *,
    db: Session = Depends(deps.get_db),
    department: str,
    date: str = Query(..., description="Дата (YYYY-MM-DD)"),
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить расписание отделения на определенную дату
    """
    schedule = appointment_crud.get_department_schedule(
        db, department=department, date=date
    )
    return schedule


# Сохраняем существующие endpoints для совместимости
@router.post(
    "/open-day", name="open_day", dependencies=[Depends(deps.require_roles("Admin"))]
)
def open_day(
    department: str = Query(..., description="Например ENT"),
    date_str: str = Query(..., description="YYYY-MM-DD"),
    start_number: int = Query(..., ge=0),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),  # просто чтобы токен проверился
):
    """
    Открывает день для онлайн-очереди:
    - queue::{dep}::{date}::open = 1
    - queue::{dep}::{date}::start_number = {start_number}
    (last_ticket не трогаем; будет устанавливаться по мере выдачи талонов)
    """
    key_prefix = f"{department}::{date_str}"

    _upsert_queue_setting(db, f"{key_prefix}::open", "1")
    _upsert_queue_setting(db, f"{key_prefix}::start_number", str(start_number))
    db.commit()

    # вернём понятный ответ + сводку
    stats = load_stats(db, department=department, date_str=date_str)
    # Отправляем broadcast в WebSocket
    try:
        logger.debug("Attempting to import _broadcast...")
        logger.debug("_broadcast imported successfully")
        logger.debug(
            "Calling _broadcast(department=%s, date_str=%s, stats=%s)",
            department,
            date_str,
            stats,
        )
        logger.debug("Stats object: %s, type: %s", stats, type(stats))
        _broadcast(department, date_str, stats)
        logger.debug("_broadcast called successfully")
    except Exception as e:
        # Не роняем запрос, если broadcast не удался
        logger.warning("Broadcast error in open_day: %s", e, exc_info=True)
    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "start_number": start_number,
        "is_open": True,
        "last_ticket": getattr(stats, "last_ticket", None),
        "waiting": getattr(stats, "waiting", None),
        "serving": getattr(stats, "serving", None),
        "done": getattr(stats, "done", None),
    }


@router.get("/stats", name="stats")
def stats(
    department: str = Query(...),
    # принимаем все варианты имени даты; внутри нормализуем к одной строке
    date_str: str | None = Query(None),
    date: str | None = Query(None),
    d: str | None = Query(None),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    eff_date = _pick_date(date_str, date, d)
    s = load_stats(db, department=department, date_str=eff_date)
    # load_stats обычно возвращает dataclass DayStats — распакуем атрибуты
    return {
        "department": department,
        "date_str": eff_date,
        "is_open": getattr(s, "is_open", False),
        "start_number": getattr(s, "start_number", 0),
        "last_ticket": getattr(s, "last_ticket", 0),
        "waiting": getattr(s, "waiting", 0),
        "serving": getattr(s, "serving", 0),
        "done": getattr(s, "done", 0),
    }


@router.post(
    "/close", name="close_day", dependencies=[Depends(deps.require_roles("Admin"))]
)
def close_day(
    department: str = Query(..., description="Например ENT"),
    date_str: str = Query(..., description="YYYY-MM-DD"),
    db: Session = Depends(deps.get_db),
    current_user=Depends(deps.get_current_user),
):
    """
    Закрывает утренний онлайн-набор (кнопка «Открыть приём сейчас»).
    Фактически выставляет OnlineDay.is_open = False для department+date.
    """
    get_or_create_day(db, department=department, date_str=date_str, open_flag=False)
    db.commit()
    s = load_stats(db, department=department, date_str=date_str)
    return {
        "ok": True,
        "department": department,
        "date_str": date_str,
        "is_open": s.is_open,
        "start_number": s.start_number,
        "last_ticket": s.last_ticket,
        "waiting": s.waiting,
        "serving": s.serving,
        "done": s.done,
    }


@router.get("/qrcode", name="qrcode_png")
def qrcode_png(
    department: str = Query(...),
    date_str: str | None = Query(None),
    date: str | None = Query(None),
    d: str | None = Query(None),
    current_user=Depends(deps.get_current_user),
):
    """
    Маршрут-заглушка: возвращаем данные для фронта, где уже рисуется QR
    (если у тебя есть реальная генерация PNG — просто замени реализацию тут).
    """
    eff_date = _pick_date(date_str, date, d)
    payload = f"{department}::{eff_date}"
    return {"format": "text", "data": payload}


@router.get("/{appointment_id}", response_model=appointment_schemas.Appointment)
def get_appointment(
    *,
    db: Session = Depends(deps.get_db),
    appointment_id: int,
    current_user: User = Depends(deps.get_current_user),
):
    """
    Получить запись на прием по ID
    """
    appointment = appointment_crud.get(db, id=appointment_id)
    if not appointment:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    _ensure_appointment_record_access(db, appointment, current_user)
    return appointment

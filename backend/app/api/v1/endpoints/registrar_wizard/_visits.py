from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.registrar_wizard._cart import *  # noqa
from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa
from app.api.v1.endpoints.registrar_wizard._helpers import (
    _ensure_visit_doctor_access,
    _normalize_registration_discount_mode,
    _resolve_payment_truth,
)  # noqa: F401
from app.api.v1.endpoints.registrar_wizard._settings import VisitResponse  # noqa
from app.crud.clinic import clinic_today as _clinic_today  # noqa: F401
from app.models.online_queue import OnlineQueueEntry
from app.services.visit_confirmation_service import _as_aware_utc  # noqa: F401
from app.services.visit_lifecycle_service import VisitNotFoundError  # noqa: F401


@router.get("/registrar/visits", response_model=list[VisitResponse])
def get_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "derma",
            "dentist",
            "Cashier",
            "Lab",
        )
    ),
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    patient_id: int | None = Query(None, description="Фильтр по ID пациента"),
    doctor_id: int | None = Query(None, description="Фильтр по ID врача"),
    department: str | None = Query(None, description="Фильтр по отделению"),
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
):
    """Получить объединенный список записей из таблиц visits (новый мастер) и appointments (старый мастер)"""
    try:
        from app.models.appointment import Appointment
        from app.models.clinic import Doctor
        from app.models.patient import Patient
        from app.models.service import Service
        from app.models.visit import Visit, VisitService

        result = []

        # 1. ПОЛУЧАЕМ ЗАПИСИ ИЗ СТАРОЙ ТАБЛИЦЫ APPOINTMENTS
        try:
            appointments_query = db.query(Appointment)

            # Фильтры для appointments
            if patient_id:
                appointments_query = appointments_query.filter(
                    Appointment.patient_id == patient_id
                )
            if doctor_id:
                appointments_query = appointments_query.filter(
                    Appointment.doctor_id == doctor_id
                )
            if department:
                appointments_query = appointments_query.filter(
                    Appointment.department == department
                )
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(
                        Appointment.appointment_date >= from_date
                    )
                except ValueError:
                    pass
            if date_to:
                try:
                    to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(
                        Appointment.appointment_date <= to_date
                    )
                except ValueError:
                    pass

            appointments = (
                appointments_query.order_by(Appointment.created_at.desc())
                .limit(limit)
                .all()
            )

            # Обрабатываем записи из appointments
            for appointment in appointments:
                # Получаем данные пациента
                patient_fio = f"Пациент #{appointment.patient_id}"
                patient_phone = None
                try:
                    if appointment.patient_id:
                        patient = (
                            db.query(Patient)
                            .filter(Patient.id == appointment.patient_id)
                            .first()
                        )
                        if patient:
                            patient_fio = patient.short_name()
                            patient_phone = patient.phone
                except Exception:
                    pass

                result.append(
                    VisitResponse(
                        id=appointment.id
                        + 10000,  # Добавляем смещение чтобы избежать конфликтов ID
                        patient_id=appointment.patient_id,
                        patient_fio=patient_fio,
                        patient_phone=patient_phone,
                        doctor_id=appointment.doctor_id,
                        doctor_name=None,
                        doctor_specialty=None,
                        department=appointment.department,
                        visit_date=appointment.appointment_date,
                        visit_time=appointment.appointment_time,
                        status=appointment.status,
                        discount_mode="none",
                        approval_status="approved",
                        services=appointment.services or [],
                        notes=appointment.notes,
                        created_at=appointment.created_at,
                    )
                )
        except Exception as e:
            logger.error("Error processing appointments: %s", e, exc_info=True)

        # 2. ПОЛУЧАЕМ ЗАПИСИ ИЗ НОВОЙ ТАБЛИЦЫ VISITS
        visits_query = db.query(Visit)

        # Фильтры для visits
        if patient_id:
            visits_query = visits_query.filter(Visit.patient_id == patient_id)
        if doctor_id:
            visits_query = visits_query.filter(Visit.doctor_id == doctor_id)
        if department:
            visits_query = visits_query.filter(Visit.department == department)
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

        # Обрабатываем записи из visits
        for visit in visits:
            # Получаем услуги визита
            visit_services = (
                db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            )
            service_names = []
            for vs in visit_services:
                if vs.name:  # Используем сохраненное имя
                    service_names.append(vs.name)
                else:  # Fallback - ищем в таблице services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service:
                        service_names.append(service.name)

            # Получаем данные врача
            doctor_name = None
            doctor_specialty = None
            if visit.doctor_id:
                doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first()
                if doctor:
                    # [OK] ИСПРАВЛЕНО: User имеет full_name, а не first_name/last_name
                    if doctor.user_id:
                        user = db.query(User).filter(User.id == doctor.user_id).first()
                        doctor_name = (
                            (user.full_name or user.username)
                            if user
                            else f"Врач #{doctor.id}"
                        )
                    else:
                        doctor_name = f"Врач #{doctor.id}"
                    doctor_specialty = doctor.specialty

            # Получаем данные пациента
            patient_fio = f"Пациент #{visit.patient_id}"
            patient_phone = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
                if patient:
                    patient_fio = patient.short_name()
                    patient_phone = patient.phone

            result.append(
                VisitResponse(
                    id=visit.id,
                    patient_id=visit.patient_id,
                    patient_fio=patient_fio,
                    patient_phone=patient_phone,
                    doctor_id=visit.doctor_id,
                    doctor_name=doctor_name,
                    doctor_specialty=doctor_specialty,
                    department=visit.department,
                    visit_date=visit.visit_date,
                    visit_time=visit.visit_time,
                    status=visit.status,
                    discount_mode=visit.discount_mode,
                    approval_status=visit.approval_status,
                    services=service_names,
                    notes=visit.notes,
                    created_at=visit.created_at,
                )
            )

        # Сортируем объединенный результат по дате создания
        result.sort(key=lambda x: x.created_at, reverse=True)

        # Применяем пагинацию к объединенному результату
        total_results = result[skip : skip + limit]

        return total_results

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ПРОСТОЙ ЭНДПОИНТ ДЛЯ ОБЪЕДИНЕНИЯ ДАННЫХ =====================


def _serialize_appointments_for_listing(
    db: Session,
    date_from: str | None,
    date_to: str | None,
    search: str | None,
    limit: int,
    offset: int,
):
    """Fetch and serialize Appointment records for the all-appointments listing."""
    from datetime import datetime

    from sqlalchemy import func, or_

    from app.models.appointment import Appointment
    from app.models.patient import Patient

    # 1. Получаем старые appointments с фильтрацией
    appointments_query = db.query(Appointment)

    # Применяем фильтры по дате
    if date_from:
        try:
            from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
            appointments_query = appointments_query.filter(
                Appointment.appointment_date >= from_date
            )
        except ValueError:
            pass
    if date_to:
        try:
            to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
            appointments_query = appointments_query.filter(
                Appointment.appointment_date <= to_date
            )
        except ValueError:
            pass

    patient_search_name = func.trim(
        func.coalesce(Patient.last_name, "")
        + literal(" ")
        + func.coalesce(Patient.first_name, "")
        + literal(" ")
        + func.coalesce(Patient.middle_name, "")
    )

    # Применяем поиск
    if search:
        # Для поиска по телефону извлекаем только цифры
        search_digits = ''.join(filter(str.isdigit, search))

        if search_digits:
            # Поиск по ФИО, телефону и ID записи (включая только цифры)
            appointments_query = appointments_query.join(
                Patient, Appointment.patient_id == Patient.id
            ).filter(
                or_(
                    patient_search_name.ilike(f"%{search}%"),
                    Patient.phone.ilike(f"%{search}%"),
                    func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(
                        f"%{search_digits}%"
                    ),
                    Appointment.id.cast(String).ilike(f"%{search_digits}%"),
                )
            )
        else:
            # Если нет цифр, ищем только по ФИО
            appointments_query = appointments_query.join(
                Patient, Appointment.patient_id == Patient.id
            ).filter(patient_search_name.ilike(f"%{search}%"))

    appointments = (
        appointments_query.order_by(Appointment.created_at.desc())
        .limit(limit // 2)
        .all()
    )
    result = []
    for apt in appointments:
        related_visit = None
        # Получаем имя пациента
        patient_fio = None
        if apt.patient_id:
            patient = db.query(Patient).filter(Patient.id == apt.patient_id).first()
            if patient:
                patient_fio = patient.short_name()

        # Преобразуем ID услуг в названия для appointments
        service_names = []
        service_codes = []
        total_amount = 0

        if apt.services and isinstance(apt.services, list):
            from app.models.service import Service

            for service_id in apt.services:
                try:
                    service_id_int = int(service_id)
                    service = (
                        db.query(Service).filter(Service.id == service_id_int).first()
                    )
                    if service:
                        service_names.append(service.name)
                        service_code = service.service_code or get_service_code(
                            service.id, db
                        )
                        if service_code:
                            service_codes.append(service_code)
                        if service.price:
                            total_amount += float(service.price)
                except (ValueError, TypeError):
                    # Если service_id не число, возможно это уже название
                    service_names.append(str(service_id))

        # Определяем payment_status для Appointment по Payment table.
        try:
            from sqlalchemy import and_

            related_visit = (
                db.query(Visit)
                .filter(
                    and_(
                        Visit.patient_id == apt.patient_id,
                        Visit.visit_date == apt.appointment_date,
                        Visit.doctor_id == apt.doctor_id,
                    )
                )
                .first()
            )
        except Exception:
            related_visit = None

        visit_type = _normalize_registration_discount_mode(
            getattr(apt, 'visit_type', None)
        )
        appointment_payment_processed_at = getattr(apt, 'payment_processed_at', None)
        payment_status, payment_type = _resolve_payment_truth(
            db,
            visit_id=related_visit.id if related_visit else None,
            legacy_paid_at=appointment_payment_processed_at,
        )

        result.append(
            {
                'id': apt.id,
                'appointment_id': apt.id,
                'visit_id': related_visit.id if related_visit else None,
                'patient_id': apt.patient_id,
                'patient_fio': patient_fio,
                'doctor_id': apt.doctor_id,
                'department': apt.department,
                'appointment_date': apt.appointment_date,
                'appointment_time': apt.appointment_time,
                'status': _preserve_operational_status_on_payment(apt.status),
                'services': service_names,  # Преобразованные названия услуг
                'service_codes': service_codes,  # Коды услуг для фильтрации
                'total_amount': total_amount,  # Общая сумма услуг
                'payment_status': payment_status,  # [OK] ДОБАВЛЕНО: Статус оплаты
                'payment_type': payment_type,
                'visit_type': visit_type,  # Тип визита для совместимости
                'notes': apt.notes,
                'created_at': apt.created_at,
                'source': 'appointments',
                'queue_numbers': [],  # Старые appointments не имеют номеров в новых очередях
                'confirmation_status': 'none',  # Старые appointments не требуют подтверждения
                'confirmed_at': None,
                'confirmed_by': None,
            }
        )

    return result


def _serialize_visits_for_listing(
    db: Session,
    date_from: str | None,
    date_to: str | None,
    search: str | None,
    limit: int,
    offset: int,
):
    """Fetch and serialize Visit records for the all-appointments listing."""
    from datetime import datetime

    from sqlalchemy import func, or_

    from app.models.patient import Patient
    from app.models.visit import Visit

    # 2. Получаем новые visits с фильтрацией
    visits_query = db.query(Visit)

    # Применяем фильтры по дате
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

    # Применяем поиск
    if search:
        # Для поиска по телефону извлекаем только цифры
        search_digits = ''.join(filter(str.isdigit, search))

        if search_digits:
            # Поиск по ФИО, телефону и ID записи (включая только цифры)
            visits_query = visits_query.join(
                Patient, Visit.patient_id == Patient.id
            ).filter(
                or_(
                    Patient.full_name.ilike(f"%{search}%"),
                    Patient.phone.ilike(f"%{search}%"),
                    func.regexp_replace(Patient.phone, r'[^\d]', '', 'g').ilike(
                        f"%{search_digits}%"
                    ),
                    Visit.id.cast(String).ilike(f"%{search_digits}%"),
                )
            )
        else:
            # Если нет цифр, ищем только по ФИО
            visits_query = visits_query.join(
                Patient, Visit.patient_id == Patient.id
            ).filter(Patient.full_name.ilike(f"%{search}%"))

    visits = visits_query.order_by(Visit.created_at.desc()).limit(limit // 2).all()
    result = []
    for visit in visits:
        # Получаем имя пациента
        patient_fio = None
        if visit.patient_id:
            patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
            if patient:
                patient_fio = patient.short_name()

        # Получаем услуги визита
        from app.models.service import Service
        from app.models.visit import VisitService

        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )
        service_names = []
        service_codes = []
        total_amount = 0

        for vs in visit_services:
            service_price = 0
            if vs.price is not None:  # Используем сохраненную цену (включая 0)
                service_price = float(vs.price)
            elif vs.service_id:  # Fallback - ищем цену в таблице services
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                if service and service.price:
                    service_price = float(service.price)

            total_amount += service_price * (vs.qty or 1)

            if vs.name:  # Используем сохраненное имя
                service_names.append(vs.name)
                if vs.code:
                    service_codes.append(normalize_service_code(vs.code))
            else:  # Fallback - ищем в таблице services
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                if service:
                    service_names.append(service.name)
                    service_code = service.service_code or get_service_code(
                        service.id, db
                    )
                    if service_code:
                        service_codes.append(service_code)

        # Получаем информацию о номерах в очередях для визита
        queue_numbers = []
        confirmation_status = None

        if visit.visit_date == _clinic_today(db):
            # Ищем записи в очередях для этого визита
            from app.models.online_queue import DailyQueue, OnlineQueueEntry

            queue_entries = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.visit_id == visit.id)
                .all()
            )

            for entry in queue_entries:
                queue = (
                    db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
                )
                if queue:
                    queue_names = {
                        "ecg": "ЭКГ",
                        "cardiology_common": "Кардиолог",
                        "dermatology": "Дерматолог",
                        "stomatology": "Стоматолог",
                        "cosmetology": "Косметолог",
                        "lab": "Лаборатория",
                        "general": "Общая очередь",
                    }

                    queue_numbers.append(
                        {
                            "queue_tag": queue.queue_tag or "general",
                            "queue_name": queue_names.get(
                                queue.queue_tag or "general",
                                queue.queue_tag or "Общая",
                            ),
                            "number": entry.number,
                            "status": entry.status,
                        }
                    )

        # Определяем статус подтверждения
        if visit.status == "pending_confirmation":
            confirmation_status = "pending"
        elif visit.confirmed_at:
            confirmation_status = "confirmed"
        else:
            confirmation_status = "none"

        payment_status, payment_type = _resolve_payment_truth(
            db,
            visit_id=visit.id,
            legacy_paid_at=getattr(visit, 'payment_processed_at', None),
        )
        discount_mode = _normalize_registration_discount_mode(
            getattr(visit, 'discount_mode', None)
        )

        result.append(
            {
                'id': visit.id + 20000,  # Смещение для избежания конфликтов
                'appointment_id': None,
                'visit_id': visit.id,
                'patient_id': visit.patient_id,
                'patient_fio': patient_fio,
                'doctor_id': visit.doctor_id,
                'department': visit.department,
                'appointment_date': visit.visit_date,
                'appointment_time': visit.visit_time,
                'status': _preserve_operational_status_on_payment(visit.status),
                'services': service_names,  # Реальные названия услуг
                'service_codes': service_codes,  # Коды услуг для фильтрации
                'total_amount': total_amount,  # Общая сумма услуг
                'payment_status': payment_status,  # [OK] ДОБАВЛЕНО: Статус оплаты
                'payment_type': payment_type,
                'discount_mode': discount_mode,  # Тип визита для отображения
                'approval_status': visit.approval_status,  # [OK] ДОБАВЛЕНО: Статус одобрения для all_free
                'notes': visit.notes,
                'created_at': visit.created_at,
                'source': 'visits',
                'queue_numbers': queue_numbers,  # Номера в очередях
                'confirmation_status': confirmation_status,  # Статус подтверждения
                'confirmed_at': (
                    visit.confirmed_at.isoformat() if visit.confirmed_at else None
                ),
                'confirmed_by': visit.confirmed_by,
            }
        )

    # Сортируем по дате создания
    result.sort(key=lambda x: x['created_at'], reverse=True)

    # Применяем пагинацию
    paginated_result = result[offset : offset + limit]

    return result


@router.get("/registrar/all-appointments", response_model=dict[str, Any])
def get_all_appointments(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Doctor",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
            "Lab",
        )
    ),
    limit: int = Query(200, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    date_from: str | None = Query(None, description="Дата начала (YYYY-MM-DD)"),
    date_to: str | None = Query(None, description="Дата окончания (YYYY-MM-DD)"),
    search: str | None = Query(None, description="Поиск по ФИО, телефону или услугам"),
):
    """Простое объединение appointments + visits для фронтенда"""
    try:
        appointments = _serialize_appointments_for_listing(
            db=db,
            date_from=date_from,
            date_to=date_to,
            search=search,
            limit=limit,
            offset=offset,
        )

        visits = _serialize_visits_for_listing(
            db=db,
            date_from=date_from,
            date_to=date_to,
            search=search,
            limit=limit,
            offset=offset,
        )

        result = appointments + visits

        return {
            "data": result,
            "total": len(result),
            "limit": limit,
            "offset": offset,
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ЭНДПОИНТ ДЛЯ ОТМЕТКИ ЗАПИСЕЙ ИЗ VISITS КАК ОПЛАЧЕННЫХ =====================


def _preserve_operational_status_on_payment(raw_status: str | None) -> str:
    """Payment is stored separately; old status='paid' data stays in the queue as waiting."""
    if not raw_status or raw_status == "paid":
        return "waiting"
    return raw_status


def _sync_payment_invoices_for_paid_visit(
    db: Session,
    *,
    visit_id: int,
    payment_method: str,
) -> None:
    """Close an invoice only after every linked visit's debt is settled."""
    from app.services.payment_invariant_service import PaymentInvariantService

    service = PaymentInvariantService(db)
    links = (
        db.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.visit_id == visit_id)
        .all()
    )
    for invoice_id in sorted({link.invoice_id for link in links}):
        invoice = (
            db.query(PaymentInvoice)
            .filter(PaymentInvoice.id == invoice_id)
            .with_for_update()
            .populate_existing()
            .first()
        )
        if not invoice or invoice.status not in {"pending", "processing"}:
            continue
        visits = [item.visit for item in invoice.visits]
        if visits and service.summarize_visits(visits)["remaining_amount"] == 0:
            invoice.status = "paid"
            invoice.payment_method = payment_method or invoice.payment_method
            invoice.paid_at = datetime.now(UTC)


REGISTRAR_COMMAND_ROLE_BY_ACTION = {
    "mark_paid": {"admin", "registrar", "cashier"},
    "start_visit": {
        "doctor",
        "cardio",
        "cardiology",
        "cardiologist",
        "derma",
        "dermatologist",
        "dentist",
        "lab",
    },
    "complete": {
        "doctor",
        "cardio",
        "cardiology",
        "cardiologist",
        "derma",
        "dermatologist",
        "dentist",
        "lab",
    },
    "cancel": {"admin", "registrar", "cashier", "doctor"},
}

REGISTRAR_SUPPORTED_RECORD_KINDS = {"visit", "online_queue", "appointment"}
REGISTRAR_APPOINTMENT_WORKFLOW_ROLES = {"admin", "registrar"}


def _registrar_user_role_names(user: User | None) -> set[str]:
    role_names: set[str] = set()
    primary_role = getattr(user, "role", None)
    if primary_role:
        role_names.add(str(primary_role).strip().lower())

    for role in getattr(user, "roles", None) or []:
        role_name = getattr(role, "name", None)
        if role_name:
            role_names.add(str(role_name).strip().lower())

    return role_names


def _normalize_registrar_action(action: str | None) -> str:
    return str(action or "").strip().lower().replace("-", "_")


def _normalize_registrar_record_kind(record_kind: str | None) -> str:
    return str(record_kind or "").strip().lower()


def _registrar_command_allowed_roles(
    action: str,
    record_kind: str | None = None,
) -> set[str] | None:
    if record_kind == "appointment" and action in {"start_visit", "complete"}:
        return REGISTRAR_APPOINTMENT_WORKFLOW_ROLES
    return REGISTRAR_COMMAND_ROLE_BY_ACTION.get(action)


def _ensure_registrar_command_role(
    user: User | None,
    action: str,
    record_kind: str | None = None,
) -> None:
    allowed_roles = _registrar_command_allowed_roles(action, record_kind)
    if not allowed_roles:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported registrar action: {action}",
        )
    if not (_registrar_user_role_names(user) & allowed_roles):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Action is not available for this user",
        )


def _registrar_command_item(
    *,
    record_kind: str,
    record_id: int,
    success: bool,
    skipped: bool = False,
    status_value: str | None = None,
    payment_status: str | None = None,
    error: str | None = None,
    result: dict[str, Any] | None = None,
) -> RegistrarRecordActionItemResponse:
    return RegistrarRecordActionItemResponse(
        record_kind=record_kind,
        record_id=record_id,
        success=success,
        skipped=skipped,
        status=status_value,
        payment_status=payment_status,
        error=error,
        result=result,
    )


def _run_single_registrar_record_action(
    *,
    db: Session,
    current_user: User,
    record: RegistrarRecordRef,
    action: str,
    request: RegistrarRecordActionRequest,
) -> RegistrarRecordActionItemResponse:
    record_kind = _normalize_registrar_record_kind(record.record_kind)
    record_id = record.record_id

    if record_kind not in REGISTRAR_SUPPORTED_RECORD_KINDS:
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error="unsupported_record_kind",
        )

    try:
        if action == "mark_paid":
            if record_kind == "visit":
                result = mark_visit_as_paid(
                    record_id,
                    payment_req=MarkPaidRequest(
                        amount=request.amount,
                        method=request.method,
                    ),
                    db=db,
                    current_user=current_user,
                )
            elif record_kind == "online_queue":
                result = mark_queue_entry_as_paid(
                    record_id,
                    payment_req=MarkPaidRequest(
                        amount=request.amount,
                        method=request.method,
                    ),
                    db=db,
                    current_user=current_user,
                )
            else:
                appointment = crud_appointment.get(db, id=record_id)
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                if str(appointment.status or "").lower() == "paid":
                    return _registrar_command_item(
                        record_kind=record_kind,
                        record_id=record_id,
                        success=True,
                        skipped=True,
                        status_value=appointment.status,
                        payment_status="paid",
                    )
                appointment = crud_appointment.mark_paid(db, appointment_id=record_id)
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {
                    "id": appointment.id,
                    "status": appointment.status,
                    "payment_status": "paid",
                }
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(result.get("status") or ""),
                payment_status=str(result.get("payment_status") or "") or None,
                result=result,
            )

        if action == "cancel":
            if record_kind == "visit":
                # Gate C bypass fix: delegate to VisitLifecycleService.cancel_visit()
                # instead of VisitsApiService.set_status().
                #
                # The old code (VisitsApiService.set_status) bypassed the state
                # machine — it did NOT call is_valid_visit_transition(), allowing
                # invalid transitions like completed→canceled, closed→canceled,
                # expired→canceled. These silently broke financial/EMR invariants
                # (a completed visit has clinical work done; a closed visit has
                # EMR signed + payment collected).
                #
                # VisitLifecycleService.cancel_visit() provides:
                #   - SELECT FOR UPDATE row lock (concurrency safety)
                #   - is_valid_visit_transition() validation (state machine)
                #   - Audit logging (logger.info with visit_id, user_id, reason)
                #   - commit=False for caller-controlled transaction
                #
                # If the transition is invalid (e.g. completed→canceled), the
                # service raises HTTPException(409), which is caught by the
                # outer except HTTPException → returns success=False with error.
                from app.services.visit_lifecycle_service import VisitLifecycleService

                visit = VisitLifecycleService(db).cancel_visit(
                    visit_id=record_id,
                    current_user=current_user,
                    reason=request.reason,
                    commit=False,  # caller owns the transaction
                )
                if request.reason:
                    visit.notes = (visit.notes or "") + f"\nCanceled: {request.reason}"
                # Cascade cancel to queue entries (preserves behavior of the
                # old VisitsApiService.set_status which did this internally).
                # Uses commit=False — the cascade is staged in the same
                # transaction as the visit status change.
                try:
                    from app.api.v1.endpoints.visits import (
                        _update_queue_entries_for_visit_owner,
                    )

                    _update_queue_entries_for_visit_owner(
                        db,
                        visit_id=record_id,
                        patient_id=visit.patient_id,
                        status_value="canceled",
                    )
                except Exception:
                    # Queue cascade failure must not block visit cancellation
                    # (same behavior as the old code).
                    pass
                db.commit()
                db.refresh(visit)
                result = {"id": visit.id, "status": visit.status}
            elif record_kind == "online_queue":
                # Codex R13 PR 3121 (P2): каскад получает актёра и причину —
                # VisitLifecycleService логирует отмену с user_id и дописывает
                # причину в notes визита. Раньше обе поверхности теряли
                # контекст: без user_id в аудите и с молча выброшенной
                # причиной.
                entry = OnlineQueueNewService(db).cancel_entry(
                    entry_id=record_id,
                    current_user=current_user,
                    reason=request.reason,
                )
                result = {"id": entry.id, "status": entry.status}
            else:
                appointment = crud_appointment.cancel_appointment(
                    db,
                    appointment_id=record_id,
                )
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {"id": appointment.id, "status": appointment.status}
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(result.get("status") or ""),
                result=result,
            )

        if action == "start_visit":
            if record_kind == "appointment":
                appointment = crud_appointment.start_visit(db, appointment_id=record_id)
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {"id": appointment.id, "status": appointment.status}
            elif record_kind == "visit":
                result = start_visit(record_id, db=db, current_user=current_user)
            else:
                from app.api.v1.endpoints.registrar_integration import start_queue_visit

                result = start_queue_visit(
                    record_id,
                    db=db,
                    current_user=current_user,
                )
            status_value = None
            if isinstance(result, dict):
                status_value = result.get("status") or (result.get("entry") or {}).get(
                    "status"
                )
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(status_value or ""),
                result=result if isinstance(result, dict) else None,
            )

        if action == "complete":
            if record_kind == "appointment":
                appointment = crud_appointment.complete_visit(
                    db, appointment_id=record_id
                )
                if not appointment:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail="Appointment not found",
                    )
                result = {"id": appointment.id, "status": appointment.status}
            elif record_kind == "visit":
                result = complete_visit(record_id, db=db, current_user=current_user)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Complete is not available for online queue records",
                )
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(result.get("status") or ""),
                result=result if isinstance(result, dict) else None,
            )

    except OnlineQueueNewDomainError as exc:
        # Codex R13 PR 3121 (P1): отклонённый record НЕ оставляет staged-
        # изменений в сессии — иначе следующий успешный record этого же
        # batch-запроса закоммитил бы и чужой каскад (визит, staged как
        # canceled до отказа финансовых гардов, коммитился вместе с ним).
        db.rollback()
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error=exc.detail,
        )
    except VisitNotFoundError:
        # P2 #5 fix (PR 2725): VisitNotFoundError is raised by
        # VisitLifecycleService._load_visit_for_update() when a visit
        # ID doesn't exist. It's a VisitLifecycleError(Exception), NOT
        # an HTTPException — so the except HTTPException above does NOT
        # catch it. Without this catch, the exception propagates out of
        # _run_single, aborts the batch list comprehension, and reaches
        # FastAPI's global handler as HTTP 500.
        #
        # This was a REGRESSION from PR #2719: the old VisitsApiService
        # raised HTTPException(404) which WAS caught. The migration to
        # VisitLifecycleService introduced VisitNotFoundError which is not.
        #
        # Fix: catch it here → per-record failure (batch isolation).
        # Codex R13 PR 3121 (P1): изоляция batch — отклонённый record
        # откатывается, staged-изменения не утекают в следующий commit.
        db.rollback()
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error="Visit not found",
        )
    except HTTPException as exc:
        # Codex R13 PR 3121 (P1): изоляция batch — rollback отклонённого
        # record до ответа, следующий record стартует с чистой сессией.
        db.rollback()
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error=str(exc.detail),
        )

    return _registrar_command_item(
        record_kind=record_kind,
        record_id=record_id,
        success=False,
        error="unsupported_action",
    )


# ============================================================
# === MARK-PAID ENDPOINTS ===
# ============================================================


def _payment_visit_ids(db: Session, records: list[RegistrarRecordRef]) -> list[int]:
    """Resolve identities on the server; never infer a visit by patient/date."""
    visit_ids = set()
    for record in records:
        if record.record_kind == "visit":
            visit_ids.add(record.record_id)
        elif record.record_kind == "online_queue":
            entry = db.get(OnlineQueueEntry, record.record_id)
            if not entry:
                raise HTTPException(404, "Queue entry not found")
            visit = db.get(Visit, entry.visit_id) if entry.visit_id else None
            if visit and visit.patient_id != entry.patient_id:
                raise HTTPException(
                    409, "Queue entry visit does not belong to the queue patient"
                )
            if not visit:
                raise HTTPException(
                    409, "Для оплаты нужна запись очереди с корректно связанным визитом"
                )
            visit_ids.add(visit.id)
        else:
            raise HTTPException(
                409, "Для учёта оплаты и долга необходимо оформить визит"
            )
    visits = db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
    if not visit_ids or len(visits) != len(visit_ids):
        raise HTTPException(404, "Visits not found")
    if len({visit.patient_id for visit in visits}) != 1:
        raise HTTPException(400, "Payment requires visits from exactly one patient")
    return sorted(visit_ids)


@router.post(
    "/registrar/records/payment-summary", response_model=RegistrarPaymentSummary
)
def get_registrar_payment_summary(
    request: RegistrarPaymentSummaryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
):
    from app.services.payment_invariant_service import PaymentInvariantService

    _ensure_registrar_command_role(current_user, "mark_paid")
    visit_ids = _payment_visit_ids(db, request.records)
    visits = db.query(Visit).filter(Visit.id.in_(visit_ids)).all()
    return PaymentInvariantService(db).summarize_visits(visits)


def _receive_registrar_payment(
    db: Session,
    current_user: User,
    records: list[RegistrarRecordRef],
    payment_req: MarkPaidRequest,
) -> RegistrarRecordActionResponse:
    from app.services.payment_invariant_service import PaymentInvariantService
    from app.services.visit_lifecycle_service import VisitLifecycleService

    _ensure_registrar_command_role(current_user, "mark_paid")
    try:
        visit_ids = _payment_visit_ids(db, records)
        method = str(payment_req.method or "cash").strip().lower()
        visits, payments, summary = PaymentInvariantService(db).receive_grouped_payment(
            visit_ids=visit_ids,
            amount=payment_req.amount,
            method=method,
            current_user=current_user,
            snapshot=payment_req.payment_snapshot,
        )
        # Serialize different visits sharing an invoice, in one consistent order.
        invoice_ids = db.query(PaymentInvoiceVisit.invoice_id).filter(
            PaymentInvoiceVisit.visit_id.in_(visit_ids)
        )
        db.query(PaymentInvoice).filter(PaymentInvoice.id.in_(invoice_ids)).order_by(
            PaymentInvoice.id
        ).with_for_update().populate_existing().all()
        for visit in visits:
            VisitLifecycleService(db).restore_operational_status_after_payment_change(
                visit_id=visit.id,
                commit=False,
            )
            _sync_payment_invoices_for_paid_visit(
                db, visit_id=visit.id, payment_method=method
            )
        balances = {row["visit_id"]: row for row in summary["visits"]}
        received = {}
        for payment in payments:
            received[payment.visit_id] = (
                received.get(payment.visit_id, Decimal("0")) + payment.amount
            )
        results = []
        reported_visits = set()
        for record in records:
            visit_id = (
                record.record_id
                if record.record_kind == "visit"
                else db.get(OnlineQueueEntry, record.record_id).visit_id
            )
            visit = next(v for v in visits if v.id == visit_id)
            balance = balances[visit_id]
            received_amount = received.get(visit_id, Decimal("0")) if visit_id not in reported_visits else Decimal("0")
            reported_visits.add(visit_id)
            results.append(
                _registrar_command_item(
                    record_kind=record.record_kind,
                    record_id=record.record_id,
                    success=True,
                    skipped=received_amount == 0,
                    status_value=visit.status,
                    payment_status=balance["payment_status"],
                    result={
                        "id": record.record_id,
                        "status": visit.status,
                        **balance,
                        "amount": received_amount,
                    },
                )
            )
        response = RegistrarRecordActionResponse(
            action="mark_paid",
            success=True,
            failed_count=0,
            success_count=sum(not item.skipped for item in results),
            skipped_count=sum(item.skipped for item in results),
            results=results,
            payment_summary=summary,
        )
        # Validate the response before committing; no database reads after commit.
        db.commit()
        return response
    except Exception:
        db.rollback()
        raise


@router.post("/registrar/visits/{visit_id}/mark-paid", response_model=dict[str, Any])
def mark_visit_as_paid(
    visit_id: int,
    payment_req: MarkPaidRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
):
    response = _receive_registrar_payment(
        db,
        current_user,
        [RegistrarRecordRef(record_kind="visit", record_id=visit_id)],
        payment_req or MarkPaidRequest(),
    )
    return response.results[0].result


@router.post(
    "/registrar/queue/entry/{entry_id}/mark-paid", response_model=dict[str, Any]
)
def mark_queue_entry_as_paid(
    entry_id: int,
    payment_req: MarkPaidRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
):
    entry = db.get(OnlineQueueEntry, entry_id)
    if not entry:
        raise HTTPException(404, "Queue entry not found")
    # Keep the old marker-only command for legacy callers with no money amount.
    # An actual receipt always requires a canonical visit owner.
    if not entry.visit_id and (payment_req is None or payment_req.amount is None):
        entry.status = _preserve_operational_status_on_payment(entry.status)
        entry.discount_mode = "paid"
        entry.updated_at = datetime.now(UTC)
        db.commit()
        return {"id": entry.id, "status": entry.status, "payment_status": "paid"}
    response = _receive_registrar_payment(
        db,
        current_user,
        [RegistrarRecordRef(record_kind="online_queue", record_id=entry_id)],
        payment_req or MarkPaidRequest(),
    )
    return response.results[0].result


@router.post("/registrar/visits/{visit_id}/complete", response_model=dict[str, Any])
def complete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Cashier", "Doctor")
    ),
):
    """Завершить запись из таблицы visits"""
    # Issue #06 (H-3 coverage gap): previously set visit.status = "completed"
    # directly, bypassing the state machine. A closed/canceled visit could
    # be moved to "completed" — the exact terminal→non-terminal transition
    # H-3 was supposed to prevent.
    #
    # Now delegates to VisitLifecycleService.transition_status(), which
    # enforces ALLOWED_VISIT_TRANSITIONS and acquires with_for_update().
    try:
        from app.models.visit import Visit
        from app.services.visit_lifecycle_service import VisitLifecycleService

        # Pre-load for access check (lifecycle service does its own load
        # with FOR UPDATE, but we need the visit object for the access
        # check first).
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
            )

        _ensure_visit_doctor_access(db, visit, current_user)

        # Transition via the state machine. Allowed: open→? (no, open can
        # only go to in_progress or canceled), in_progress→completed (yes),
        # completed→completed (idempotent). If the visit is closed/canceled,
        # this raises 409 terminal_to_non_terminal.
        visit = VisitLifecycleService(db).transition_status(
            visit_id=visit_id,
            target_status="completed",
            current_user=current_user,
        )

        return {"id": visit.id, "status": visit.status, "message": "Запись завершена"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/registrar/visits/{visit_id}/start-visit", response_model=dict[str, Any])
def start_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Начать прием (в кабинете) для записи из таблицы visits"""
    # Issue #06: delegate to VisitLifecycleService for state machine + lock.
    try:
        from app.services.visit_lifecycle_service import VisitLifecycleService

        visit = VisitLifecycleService(db).transition_status(
            visit_id=visit_id,
            target_status="in_progress",
            current_user=current_user,
        )

        return {"id": visit.id, "status": visit.status, "message": "Прием начат"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


"""
Эндпоинты подтверждения визитов
Временный файл для добавления в registrar_wizard.py
"""

# ===================== ПОДТВЕРЖДЕНИЕ ВИЗИТОВ =====================


@router.post(
    "/registrar/records/actions",
    response_model=RegistrarRecordActionResponse,
)
def run_registrar_record_action(
    request: RegistrarRecordActionRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Cashier",
            "Doctor",
            "cardio",
            "cardiology",
            "cardiologist",
            "derma",
            "dermatologist",
            "dentist",
            "Lab",
        )
    ),
) -> RegistrarRecordActionResponse:
    """Run registrar-owned record commands through a single backend contract."""

    action = _normalize_registrar_action(request.action)

    records: list[RegistrarRecordRef] = []
    if request.records:
        records.extend(request.records)
    if request.record_kind and request.record_id is not None:
        records.append(
            RegistrarRecordRef(
                record_kind=request.record_kind,
                record_id=request.record_id,
            )
        )

    unique_records: list[RegistrarRecordRef] = []
    seen: set[tuple[str, int]] = set()
    for record in records:
        record_kind = _normalize_registrar_record_kind(record.record_kind)
        key = (record_kind, record.record_id)
        if record.record_id <= 0 or key in seen:
            continue
        seen.add(key)
        unique_records.append(
            RegistrarRecordRef(record_kind=record_kind, record_id=record.record_id)
        )

    if not unique_records:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No registrar records provided",
        )

    for record in unique_records:
        _ensure_registrar_command_role(
            current_user,
            action,
            record.record_kind,
        )

    if action == "mark_paid" and request.amount is not None:
        return _receive_registrar_payment(
            db, current_user, unique_records,
            MarkPaidRequest(amount=request.amount, method=request.method,
                            payment_snapshot=request.payment_snapshot),
        )

    results = [
        _run_single_registrar_record_action(
            db=db,
            current_user=current_user,
            record=record,
            action=action,
            request=request,
        )
        for record in unique_records
    ]

    success_count = len([item for item in results if item.success and not item.skipped])
    skipped_count = len([item for item in results if item.success and item.skipped])
    failed_count = len([item for item in results if not item.success])

    return RegistrarRecordActionResponse(
        action=action,
        success=failed_count == 0,
        success_count=success_count,
        skipped_count=skipped_count,
        failed_count=failed_count,
        results=results,
    )


class ConfirmVisitRequest(BaseModel):
    confirmation_method: str = Field(default="phone", pattern="^(phone|manual)$")
    confirmed_by: str | None = None  # Номер телефона или ID сотрудника
    notes: str | None = None


class ConfirmVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    queue_numbers: dict[str, Any] | None = None
    print_tickets: list[dict[str, Any]] | None = None


@router.post(
    "/registrar/visits/{visit_id}/confirm", response_model=ConfirmVisitResponse
)
def confirm_visit_by_registrar(
    visit_id: int,
    request: ConfirmVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Подтверждение визита регистратором (по телефону)
    Присваивает номера в очередях если визит на сегодня
    """
    try:
        # Находим визит
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем что визит ожидает подтверждения
        if visit.status != "pending_confirmation":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Визит уже имеет статус: {visit.status}",
            )

        # Проверяем что токен не истек
        if visit.confirmation_expires_at and _as_aware_utc(
            visit.confirmation_expires_at
        ) < datetime.now(UTC):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок подтверждения истек",
            )

        # Подтверждаем визит
        # Issue #06 Phase 3: delegate to VisitLifecycleService.
        # confirm_visit() does pending_confirmation → confirmed.
        # If the visit is for today, activate_confirmed_visit() then
        # does confirmed → open (after queue numbers are assigned).
        from app.services.visit_lifecycle_service import VisitLifecycleService

        lifecycle = VisitLifecycleService(db)
        visit = lifecycle.confirm_visit(
            visit_id=visit.id,
            current_user=current_user,
            confirmed_by=request.confirmed_by or f"registrar_{current_user.id}",
            commit=False,  # Gate D fix: composition — single commit at end
        )

        queue_numbers = {}
        print_tickets = []

        # Если визит на сегодня (день КЛИНИКИ, не host-UTC) - присваиваем
        # номера в очередях
        if visit.visit_date == _clinic_today(db):
            from app.services.visit_confirmation_service import (
                VisitConfirmationDomainError,
            )

            try:
                queue_numbers, print_tickets = _assign_queue_numbers_on_confirmation(
                    db, visit
                )
            except VisitConfirmationDomainError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail)
            # Activate: confirmed → open (ready for appointment)
            visit = lifecycle.activate_confirmed_visit(
                visit_id=visit.id,
                current_user=current_user,
                commit=False,  # Gate D fix: composition — single commit at end
            )

        db.commit()
        db.refresh(visit)

        return ConfirmVisitResponse(
            success=True,
            message=f"Визит подтвержден. {'Номера в очередях присвоены.' if queue_numbers else 'Номера будут присвоены утром в день визита.'}",
            visit_id=visit.id,
            status=visit.status,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets,
        )

    except HTTPException:
        raise
    except Exception:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


def _assign_queue_numbers_on_confirmation(
    db: Session, visit: Visit
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Assign or reuse queue numbers through VisitConfirmationService."""
    from app.services.visit_confirmation_service import VisitConfirmationService

    service = VisitConfirmationService(db)
    queue_numbers_list, print_tickets = service.assign_queue_numbers_on_confirmation(
        visit
    )
    queue_numbers = {item["queue_tag"]: item for item in queue_numbers_list}
    return queue_numbers, print_tickets

from __future__ import annotations

from app.api.v1.endpoints.registrar_wizard._helpers import *  # noqa
from app.api.v1.endpoints.registrar_wizard._settings import VisitResponse  # noqa
from app.api.v1.endpoints.registrar_wizard._cart import *  # noqa

@router.get("/registrar/visits", response_model=list[VisitResponse])
def get_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist", "Cashier", "Lab")),
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
                appointments_query = appointments_query.filter(Appointment.patient_id == patient_id)
            if doctor_id:
                appointments_query = appointments_query.filter(Appointment.doctor_id == doctor_id)
            if department:
                appointments_query = appointments_query.filter(Appointment.department == department)
            if date_from:
                try:
                    from_date = datetime.strptime(date_from, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(Appointment.appointment_date >= from_date)
                except ValueError:
                    pass
            if date_to:
                try:
                    to_date = datetime.strptime(date_to, "%Y-%m-%d").date()
                    appointments_query = appointments_query.filter(Appointment.appointment_date <= to_date)
                except ValueError:
                    pass

            appointments = (
                appointments_query
                .order_by(Appointment.created_at.desc())
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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ПРОСТОЙ ЭНДПОИНТ ДЛЯ ОБЪЕДИНЕНИЯ ДАННЫХ =====================


@router.get("/registrar/all-appointments")
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
    search: str | None = Query(
        None, description="Поиск по ФИО, телефону или услугам"
    ),
):
    """Простое объединение appointments + visits для фронтенда"""
    try:
        from datetime import datetime

        from sqlalchemy import func, or_

        from app.models.appointment import Appointment
        from app.models.patient import Patient
        from app.models.visit import Visit

        result = []

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
                            db.query(Service)
                            .filter(Service.id == service_id_int)
                            .first()
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
        for visit in visits:
            # Получаем имя пациента
            patient_fio = None
            if visit.patient_id:
                patient = (
                    db.query(Patient).filter(Patient.id == visit.patient_id).first()
                )
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
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
                    if service and service.price:
                        service_price = float(service.price)

                total_amount += service_price * (vs.qty or 1)

                if vs.name:  # Используем сохраненное имя
                    service_names.append(vs.name)
                    if vs.code:
                        service_codes.append(normalize_service_code(vs.code))
                else:  # Fallback - ищем в таблице services
                    service = (
                        db.query(Service).filter(Service.id == vs.service_id).first()
                    )
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

            if visit.visit_date == date.today():
                # Ищем записи в очередях для этого визита
                from app.models.online_queue import DailyQueue, OnlineQueueEntry

                queue_entries = (
                    db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.visit_id == visit.id)
                    .all()
                )

                for entry in queue_entries:
                    queue = (
                        db.query(DailyQueue)
                        .filter(DailyQueue.id == entry.queue_id)
                        .first()
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

        return {
            "data": paginated_result,
            "total": len(result),
            "limit": limit,
            "offset": offset,
            "has_more": offset + limit < len(result),
        }

    except Exception as e:
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
    """Mark linked registrar invoices paid once all their visits have paid Payment rows."""
    from app.models.payment import Payment

    links = (
        db.query(PaymentInvoiceVisit)
        .filter(PaymentInvoiceVisit.visit_id == visit_id)
        .all()
    )
    for link in links:
        invoice = link.invoice
        if not invoice or invoice.status not in {"pending", "processing"}:
            continue

        visit_ids = [invoice_visit.visit_id for invoice_visit in invoice.visits]
        if not visit_ids:
            continue

        paid_visit_ids = {
            row[0]
            for row in (
                db.query(Payment.visit_id)
                .filter(
                    Payment.visit_id.in_(visit_ids),
                    Payment.status == "paid",
                )
                .distinct()
                .all()
            )
        }
        if all(invoice_visit_id in paid_visit_ids for invoice_visit_id in visit_ids):
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
    "cancel": {"admin", "registrar", "cashier", "receptionist", "doctor"},
}

REGISTRAR_SUPPORTED_RECORD_KINDS = {"visit", "online_queue", "appointment"}
REGISTRAR_APPOINTMENT_WORKFLOW_ROLES = {"admin", "registrar", "receptionist"}


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
    if (
        record_kind == "appointment"
        and action in {"start_visit", "complete"}
    ):
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
                visit = VisitsApiService(db).set_status(
                    visit_id=record_id,
                    status_new="canceled",
                )
                if request.reason:
                    visit.notes = (visit.notes or "") + f"\nCanceled: {request.reason}"
                    db.commit()
                    db.refresh(visit)
                result = {"id": visit.id, "status": visit.status}
            elif record_kind == "online_queue":
                entry = OnlineQueueNewService(db).cancel_entry(entry_id=record_id)
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
                status_value = result.get("status") or (
                    result.get("entry") or {}
                ).get("status")
            return _registrar_command_item(
                record_kind=record_kind,
                record_id=record_id,
                success=True,
                status_value=str(status_value or ""),
                result=result if isinstance(result, dict) else None,
            )

        if action == "complete":
            if record_kind == "appointment":
                appointment = crud_appointment.complete_visit(db, appointment_id=record_id)
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
        return _registrar_command_item(
            record_kind=record_kind,
            record_id=record_id,
            success=False,
            error=exc.detail,
        )
    except HTTPException as exc:
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

@router.post("/registrar/visits/{visit_id}/mark-paid")
def mark_visit_as_paid(
    visit_id: int,
    payment_req: MarkPaidRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
):
    """Отметить запись из таблицы visits как оплаченную и создать платеж (SSOT)"""
    try:
        from app.models.visit import Visit
        from app.services.billing_service import BillingService

        # Логирование для диагностики
        logger.info(
            "mark_visit_as_paid: User: %s, Role: %s, Visit ID: %d",
            current_user.username,
            current_user.role,
            visit_id,
        )

        # Находим запись
        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
            )

        # [OK] ИСПРАВЛЕНО: Проверяем, не создан ли уже платеж для этого визита
        from app.models.payment import Payment

        existing_payment = (
            db.query(Payment)
            .filter(Payment.visit_id == visit_id, Payment.status == "paid")
            .first()
        )

        requested_method = (
            str(payment_req.method).strip().lower()
            if payment_req and payment_req.method
            else "cash"
        )

        if not existing_payment:
            # [OK] ИСПРАВЛЕНО: Создаем платеж через SSOT перед пометкой визита как оплаченного
            billing_service = BillingService(db)

            # Рассчитываем сумму визита через SSOT
            total_info = billing_service.calculate_total(
                visit_id=visit_id, discount_mode=visit.discount_mode or "none"
            )
            payment_amount = float(total_info["total"])

            # [OK] ИСПРАВЛЕНО: Используем прямой SQL для создания платежа, чтобы обойти конфликт моделей
            # (BillingPayment и Payment используют одну таблицу, что вызывает проблемы)
            from sqlalchemy import text

            currency = total_info.get("currency", "UZS")
            note = f"Оплата визита {visit_id} через панель кассира"
            paid_at = datetime.now(UTC)

            # Создаем платеж через прямой SQL
            result = db.execute(  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
                text(
                    """
                    INSERT INTO payments
                    (visit_id, amount, currency, method, status, note, paid_at, created_at)
                    VALUES (:visit_id, :amount, :currency, :method, :status, :note, :paid_at, :created_at)
                """
                ),
                {
                    "visit_id": visit_id,
                    "amount": payment_amount,
                    "currency": currency,
                    "method": requested_method,
                    "status": "paid",
                    "note": note,
                    "paid_at": paid_at,
                    "created_at": paid_at,
                },
            )
            db.commit()

            # Получаем созданный платеж
            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit_id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            logger.info(
                "mark_visit_as_paid: Создан платеж ID=%d для визита %d, сумма=%s, method=%s",
                payment.id,
                visit_id,
                payment_amount,
                requested_method,
            )
        else:
            logger.warning(
                "mark_visit_as_paid: Платеж уже существует для визита %d, ID=%d",
                visit_id,
                existing_payment.id,
            )

        # [FIX:PAYMENT_STATUS] Payment must not overwrite the operational visit/queue status.
        changed_at = datetime.now(UTC)
        visit.status = _preserve_operational_status_on_payment(visit.status)
        visit.updated_at = changed_at
        _sync_payment_invoices_for_paid_visit(
            db,
            visit_id=visit.id,
            payment_method=(
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
        )
        logger.info(
            "[FIX:PAYMENT_STATUS] Visit marked paid without changing operational status: visit_id=%d, status=%s",
            visit.id,
            visit.status,
        )
        db.commit()
        db.refresh(visit)

        return {
            "id": visit.id,
            "status": visit.status,
            "payment_status": "paid",
            "payment_type": (
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
            "amount": (
                float(existing_payment.amount)
                if existing_payment and getattr(existing_payment, "amount", None) is not None
                else payment_amount
            ),
            "message": "Запись отмечена как оплаченная",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_visit_as_paid: Error: %s", str(e), exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ЭНДПОИНТ ДЛЯ ОТМЕТКИ ЗАПИСЕЙ ОНЛАЙН-ОЧЕРЕДИ КАК ОПЛАЧЕННЫХ =====================


@router.post("/registrar/queue/entry/{entry_id}/mark-paid")
def mark_queue_entry_as_paid(
    entry_id: int,
    payment_req: MarkPaidRequest | None = Body(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Cashier")),
):
    """
    Отметить запись OnlineQueueEntry как оплаченную.

    Находит связанный Visit через visit_id и оплачивает его.
    Если visit_id отсутствует, пытается найти Visit по patient_id и дате.
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit
        from app.services.billing_service import BillingService

        logger.info(
            "mark_queue_entry_as_paid: User: %s, Role: %s, Entry ID: %d",
            current_user.username,
            current_user.role,
            entry_id,
        )

        # Находим запись в очереди
        entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Запись очереди с ID {entry_id} не найдена"
            )

        # Пытаемся найти связанный Visit
        visit = None

        # 1. Через visit_id
        if entry.visit_id:
            visit = db.query(Visit).filter(Visit.id == entry.visit_id).first()
            logger.info(f"mark_queue_entry_as_paid: Найден Visit {entry.visit_id} через entry.visit_id")

        if visit and visit.patient_id != entry.patient_id:
            logger.warning(
                "mark_queue_entry_as_paid: entry visit owner mismatch entry_id=%d visit_id=%d",
                entry.id,
                visit.id,
            )
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Queue entry visit does not belong to the queue patient",
            )

        requested_method = (
            str(payment_req.method).strip().lower()
            if payment_req and payment_req.method
            else "cash"
        )

        if not visit:
            # Legacy fallback: без Visit нельзя создать Payment SSOT, поэтому оставляем queue marker.
            logger.warning(
                f"mark_queue_entry_as_paid: Visit не найден для entry {entry_id}. "
                f"Обновляем только платежный статус."
            )
            entry.status = _preserve_operational_status_on_payment(entry.status)
            entry.discount_mode = "paid"
            entry.updated_at = datetime.now(UTC)
            logger.info(
                "[FIX:PAYMENT_STATUS] Queue entry marked paid without Visit: entry_id=%d, status=%s",
                entry.id,
                entry.status,
            )
            db.commit()
            db.refresh(entry)

            return {
                "id": entry.id,
                "status": entry.status,
                "payment_status": "paid",
                "payment_type": requested_method,
                "message": "Запись в очереди отмечена как оплаченная (Visit не найден)",
            }

        # Проверяем, не создан ли уже платеж для этого визита
        from app.models.payment import Payment

        existing_payment = (
            db.query(Payment)
            .filter(Payment.visit_id == visit.id, Payment.status == "paid")
            .first()
        )

        if not existing_payment:
            # Создаем платеж через SSOT
            billing_service = BillingService(db)
            total_info = billing_service.calculate_total(
                visit_id=visit.id, discount_mode=visit.discount_mode or "none"
            )
            payment_amount = float(total_info["total"])

            from sqlalchemy import text

            currency = total_info.get("currency", "UZS")
            note = f"Оплата визита {visit.id} через запись очереди {entry_id}"
            paid_at = datetime.now(UTC)

            result = db.execute(  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
                text(
                    """
                    INSERT INTO payments
                    (visit_id, amount, currency, method, status, note, paid_at, created_at)
                    VALUES (:visit_id, :amount, :currency, :method, :status, :note, :paid_at, :created_at)
                """
                ),
                {
                    "visit_id": visit.id,
                    "amount": payment_amount,
                    "currency": currency,
                    "method": requested_method,
                    "status": "paid",
                    "note": note,
                    "paid_at": paid_at,
                    "created_at": paid_at,
                },
            )
            db.commit()

            payment = (
                db.query(Payment)
                .filter(Payment.visit_id == visit.id)
                .order_by(Payment.created_at.desc())
                .first()
            )

            logger.info(
                "mark_queue_entry_as_paid: Создан платеж ID=%d для визита %d (через entry %d), сумма=%s, method=%s",
                payment.id,
                visit.id,
                entry_id,
                payment_amount,
                requested_method,
            )
        else:
            logger.info(
                "mark_queue_entry_as_paid: Платеж уже существует для визита %d, ID=%d",
                visit.id,
                existing_payment.id,
            )

        # [FIX:PAYMENT_STATUS] Payment is stored separately; queue operational status stays intact.
        changed_at = datetime.now(UTC)
        visit.status = _preserve_operational_status_on_payment(visit.status)
        visit.updated_at = changed_at

        entry.status = _preserve_operational_status_on_payment(entry.status)
        entry.updated_at = changed_at
        _sync_payment_invoices_for_paid_visit(
            db,
            visit_id=visit.id,
            payment_method=(
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
        )
        logger.info(
            "[FIX:PAYMENT_STATUS] Queue entry marked paid without changing operational status: entry_id=%d, visit_id=%d, entry_status=%s, visit_status=%s",
            entry.id,
            visit.id,
            entry.status,
            visit.status,
        )

        db.commit()
        db.refresh(visit)
        db.refresh(entry)

        return {
            "id": entry.id,
            "visit_id": visit.id,
            "status": visit.status,
            "payment_status": "paid",
            "payment_type": (
                existing_payment.method
                if existing_payment and getattr(existing_payment, "method", None)
                else requested_method
            ),
            "amount": (
                float(existing_payment.amount)
                if existing_payment and getattr(existing_payment, "amount", None) is not None
                else payment_amount
            ),
            "message": "Запись отмечена как оплаченная",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error("mark_queue_entry_as_paid: Error: %s", str(e), exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.post("/registrar/visits/{visit_id}/complete")
def complete_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Cashier", "Receptionist", "Doctor")
    ),
):
    """Завершить запись из таблицы visits"""
    try:
        from app.models.visit import Visit

        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
            )

        _ensure_visit_doctor_access(db, visit, current_user)

        visit.status = "completed"
        visit.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(visit)

        return {"id": visit.id, "status": visit.status, "message": "Запись завершена"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/registrar/visits/{visit_id}/start-visit")
def start_visit(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """Начать прием (в кабинете) для записи из таблицы visits"""
    try:
        from app.models.visit import Visit

        visit = db.query(Visit).filter(Visit.id == visit_id).first()
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
            )

        visit.status = "in_progress"
        visit.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(visit)

        return {"id": visit.id, "status": visit.status, "message": "Прием начат"}

    except HTTPException:
        raise
    except Exception as e:
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
            "Receptionist",
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
        if (
            visit.confirmation_expires_at
            and visit.confirmation_expires_at < datetime.now(UTC)
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок подтверждения истек",
            )

        # Подтверждаем визит
        visit.confirmed_at = datetime.now(UTC)
        visit.confirmed_by = request.confirmed_by or f"registrar_{current_user.id}"
        visit.status = "confirmed"

        queue_numbers = {}
        print_tickets = []

        # Если визит на сегодня - присваиваем номера в очередях
        if visit.visit_date == date.today():
            from app.services.visit_confirmation_service import (
                VisitConfirmationDomainError,
            )

            try:
                queue_numbers, print_tickets = _assign_queue_numbers_on_confirmation(
                    db, visit
                )
            except VisitConfirmationDomainError as exc:
                raise HTTPException(status_code=exc.status_code, detail=exc.detail)
            visit.status = "open"  # Ready for appointment

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
    except Exception as e:
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

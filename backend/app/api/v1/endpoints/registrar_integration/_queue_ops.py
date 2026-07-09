from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa

from app.api.v1.endpoints.registrar_integration._helpers import (
    _normalize_registration_discount_mode,
    _serialize_registrar_datetime,
)  # noqa: F401
from app.services.queue_service import queue_service  # noqa: F401


@router.get("/registrar/queue-settings", response_model=dict[str, Any])
def get_registrar_queue_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить настройки очереди для регистратуры
    Из detail.md стр. 303-338: конфигурации очереди
    """
    try:
        queue_settings = crud_clinic.get_queue_settings(db)

        # Дополняем информацией о врачах
        doctors = crud_clinic.get_doctors(db, active_only=True)

        specialty_info = {}
        for doctor in doctors:
            if doctor.specialty not in specialty_info:
                specialty_info[doctor.specialty] = {
                    "start_number": queue_settings.get("start_numbers", {}).get(
                        doctor.specialty, 1
                    ),
                    "max_per_day": queue_settings.get("max_per_day", {}).get(
                        doctor.specialty, 15
                    ),
                    "doctors": [],
                }

            specialty_info[doctor.specialty]["doctors"].append(
                {
                    "id": doctor.id,
                    "name": (
                        doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                    ),
                    "cabinet": doctor.cabinet,
                }
            )

        return {
            "timezone": queue_settings.get("timezone", "Asia/Tashkent"),
            "queue_start_hour": queue_settings.get("queue_start_hour", 7),
            "auto_close_time": queue_settings.get("auto_close_time", "09:00"),
            "specialties": specialty_info,
            "current_time": datetime.now(UTC).isoformat(),
        }

    except (ValueError, AttributeError):
        # Ошибки валидации или доступа к атрибутам
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )
    except Exception as e:
        # Остальные ошибки (БД, сеть и т.д.)
        from sqlalchemy.exc import SQLAlchemyError

        if isinstance(e, SQLAlchemyError):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Внутренняя ошибка сервера. Подробности в журнале.",
            )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== QR КОДЫ ДЛЯ РЕГИСТРАТУРЫ =====================


@router.post("/registrar/generate-qr", response_model=dict[str, Any])
def generate_qr_for_registrar(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Генерация QR кода из регистратуры
    Из detail.md стр. 355: POST /api/online-queue/qrcode?day&specialist_id
    """
    try:
        token, token_data = queue_service.assign_queue_token(
            db,
            specialist_id=specialist_id,
            department=None,
            generated_by_user_id=current_user.id,
            target_date=day,
            is_clinic_wide=False,
        )

        # Формируем QR URL для пациентов
        qr_url = f"/pwa/queue?token={token}"

        return {
            "success": True,
            "token": token,
            "qr_url": qr_url,
            "qr_data": f"{qr_url}",  # Данные для QR кода
            "specialist": token_data["specialist_name"],
            "cabinet": token_data["cabinet"],
            "day": day.isoformat(),
            "max_slots": token_data["max_slots"],
            "current_count": token_data["current_count"],
        }

    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Internal server error")
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== ОТКРЫТИЕ ПРИЕМА =====================


@router.post("/registrar/open-reception", response_model=dict[str, Any])
def open_reception(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Открытие приема из регистратуры
    Из detail.md стр. 253: Кнопка «Открыть приём сейчас»
    """
    try:
        result = crud_queue.open_daily_queue(db, day, specialist_id)

        return {
            "success": True,
            "message": "Прием открыт, онлайн-набор закрыт",
            "opened_at": result["opened_at"],
            "online_entries_transferred": result["online_entries_count"],
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== УПРАВЛЕНИЕ ОЧЕРЕДЯМИ =====================


@router.post("/registrar/queue/{entry_id}/start-visit", response_model=dict[str, Any])
def start_queue_visit(
    entry_id: int,
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
):
    """
    Начать прием для записи в очереди (статус в процессе)
    Legacy queue endpoint accepts only OnlineQueueEntry IDs.
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit

        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )
        if not queue_entry:
            # This legacy queue route must not fall back to Visit or Appointment IDs:
            # numeric IDs can collide across tables and mutate the wrong record.
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Queue entry not found",
            )

        if queue_entry:
            linked_visit = None
            if queue_entry.visit_id:
                linked_visit = (
                    db.query(Visit).filter(Visit.id == queue_entry.visit_id).first()
                )
                if linked_visit and linked_visit.patient_id != queue_entry.patient_id:
                    logger.warning(
                        "start_queue_visit: entry visit owner mismatch entry_id=%d visit_id=%d",
                        queue_entry.id,
                        linked_visit.id,
                    )
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Queue entry visit does not belong to the queue patient",
                    )

            changed_at = datetime.now(UTC)
            queue_entry.status = "in_progress"
            queue_entry.updated_at = changed_at
            if linked_visit:
                linked_visit.status = "in_progress"
                linked_visit.updated_at = changed_at

            logger.info(
                "start_queue_visit: started queue entry %d; linked_visit_id=%s; status=%s",
                queue_entry.id,
                queue_entry.visit_id,
                queue_entry.status,
            )

            db.commit()
            db.refresh(queue_entry)
            if linked_visit:
                db.refresh(linked_visit)

            return {
                "success": True,
                "message": "Прием начат успешно",
                "entry": {
                    "id": queue_entry.id,
                    "status": queue_entry.status,
                    "patient_id": queue_entry.patient_id,
                    "visit_id": queue_entry.visit_id,
                },
            }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )



# ===================== HELPERS ДЛЯ get_today_queues (R-22 decomposition) =====================


def _parse_queue_target_date(target_date: str | None) -> date:
    """R-22: Парсинг даты для очереди. Возвращает today если невалидно."""
    from datetime import datetime
    if target_date:
        import re
        if re.match(r'^\d{4}-\d{2}-\d{2}$', target_date):
            try:
                return datetime.strptime(target_date, '%Y-%m-%d').date()
            except (ValueError, TypeError):
                pass
    return date.today()


def _normalize_department_filter(department: str | None) -> set[str] | None:
    """R-22: Нормализация department фильтра для очереди."""
    if not department:
        return None
    normalized = str(department).strip().lower()
    aliases = {
        "lab": {"lab", "laboratory"},
        "laboratory": {"lab", "laboratory"},
    }
    return aliases.get(normalized, {normalized})


def _load_queue_data_for_date(db: Session, target_day: date) -> tuple:
    """R-22: Загрузка visits, appointments и online entries для даты.

    Returns:
        tuple of (visits, appointments, online_entries)
    """
    from app.models.appointment import Appointment
    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.visit import Visit

    visits = (
        db.query(Visit)
        .filter(
            Visit.visit_date == target_day,
            ~func.lower(func.coalesce(Visit.status, "")).in_(
                REGISTRAR_HIDDEN_QUEUE_STATUSES
            ),
        )
        .all()
    )

    appointments = (
        db.query(Appointment)
        .filter(
            Appointment.appointment_date == target_day,
            ~func.lower(func.coalesce(Appointment.status, "")).in_(
                REGISTRAR_HIDDEN_QUEUE_STATUSES
            ),
        )
        .all()
    )

    online_entries = (
        db.query(OnlineQueueEntry)
        .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
        .filter(
            DailyQueue.day == target_day,
            OnlineQueueEntry.status.in_(["waiting", "called", "paid"]),
        )
        .order_by(OnlineQueueEntry.queue_time.asc(), OnlineQueueEntry.id.asc())
        .all()
    )

    return visits, appointments, online_entries




def _detect_ecg_services(services: list) -> tuple[bool, int, int]:
    """R-22: Detect ECG services in a visit's service list.

    Checks by queue_tag, service name, and service code.

    Returns:
        tuple of (has_ecg, ecg_count, non_ecg_count)
    """

    has_ecg = False
    ecg_count = 0
    non_ecg_count = 0

    for service in services:
        is_ecg = False

        # Check by queue_tag
        if service.queue_tag == 'ecg':
            is_ecg = True

        # Check by service name
        elif service.name:
            name_lower = str(service.name).lower()
            if 'экг' in name_lower or 'ecg' in name_lower:
                is_ecg = True

        # Check by service code
        if not is_ecg and service.service_code:
            code_upper = str(service.service_code).upper()
            if 'ECG' in code_upper or 'ЭКГ' in code_upper:
                is_ecg = True

        if is_ecg:
            has_ecg = True
            ecg_count += 1
        else:
            non_ecg_count += 1

    return has_ecg, ecg_count, non_ecg_count


def _ensure_specialty_queue(
    queues_by_specialty: dict,
    specialty: str,
    doctor_id: int | None,
) -> None:
    """R-22: Ensure a specialty queue exists in the grouping dict."""
    if specialty not in queues_by_specialty:
        queues_by_specialty[specialty] = {
            "entries": [],
            "doctor": None,
            "doctor_id": doctor_id,
        }


def _get_visit_queue_time(
    db: Session, visit: Any
) -> Any:
    """R-22: Get queue_time from linked OnlineQueueEntry for a visit."""
    from app.models.online_queue import OnlineQueueEntry
    try:
        queue_entry = (
            db.query(OnlineQueueEntry)
            .filter(
                OnlineQueueEntry.visit_id == visit.id,
                OnlineQueueEntry.patient_id == visit.patient_id,
            )
            .order_by(OnlineQueueEntry.id.asc())
            .first()
        )
        if queue_entry and queue_entry.queue_time:
            return queue_entry.queue_time
    except Exception:
        pass
    return None


def _get_visit_created_at(visit: Any) -> Any:
    """R-22: Get created_at from visit, preferring confirmed_at if available."""
    if hasattr(visit, 'confirmed_at') and visit.confirmed_at:
        return visit.confirmed_at
    return visit.created_at



# ===================== R-22 Phase 3: Online entries + Appointment processing =====================


_SPECIALTY_MAPPING = {
    "cardio": "cardiology",
    "cardiology": "cardiology",
    "derma": "dermatology",
    "dermatology": "dermatology",
    "dentist": "stomatology",
    "stomatology": "stomatology",
    "lab": "laboratory",
    "laboratory": "laboratory",
    "ecg": "echokg",
    "echokg": "echokg",
}


def _process_online_queue_entries(
    db: Session,
    online_entries: list,
    visits: list,
    queues_by_specialty: dict,
    seen_visit_ids: set,
) -> None:
    """R-22 Phase 3: Process OnlineQueueEntry records into specialty queues."""
    from app.models.clinic import Doctor
    from app.models.online_queue import DailyQueue

    for online_entry in online_entries:
        if online_entry.visit_id and online_entry.visit_id in seen_visit_ids:
            continue

        if not online_entry.visit_id and online_entry.patient_id:
            is_qr_entry = online_entry.source in ('online', 'confirmation')
            if not is_qr_entry:
                patient_has_visit = any(
                    v.patient_id == online_entry.patient_id for v in visits
                )
                if patient_has_visit:
                    continue

        daily_queue = (
            db.query(DailyQueue)
            .filter(DailyQueue.id == online_entry.queue_id)
            .first()
        )
        if not daily_queue:
            continue

        doctor = db.query(Doctor).filter(Doctor.id == daily_queue.specialist_id).first()
        integrity_warnings: list[str] = []
        if not doctor:
            integrity_warnings.append("linked_doctor_missing")

        specialty = None
        if daily_queue.queue_tag:
            specialty = daily_queue.queue_tag.lower()
        elif doctor and doctor.department:
            specialty = doctor.department.lower()
        else:
            specialty = "general"

        specialty = _SPECIALTY_MAPPING.get(specialty, specialty)

        if doctor and not doctor.user_id:
            integrity_warnings.append("doctor_without_user")
        if doctor and doctor.user and not doctor.user.is_active:
            integrity_warnings.append("doctor_user_inactive")
        if doctor and not doctor.active:
            integrity_warnings.append("doctor_inactive")
        if doctor and not doctor.cabinet:
            integrity_warnings.append("doctor_cabinet_missing")

        _ensure_specialty_queue(queues_by_specialty, specialty, doctor.id if doctor else daily_queue.specialist_id)
        bucket = queues_by_specialty[specialty]
        bucket.setdefault("integrity_warnings", [])
        for warning in integrity_warnings:
            if warning not in bucket["integrity_warnings"]:
                bucket["integrity_warnings"].append(warning)

        if doctor and doctor.id:
            bucket["doctor"] = doctor
            bucket["doctor_id"] = doctor.id

        entry_time = (
            online_entry.queue_time
            if online_entry.queue_time
            else (online_entry.created_at if online_entry.created_at else datetime.now())
        )

        bucket["entries"].append({
            "type": "online_queue",
            "data": online_entry,
            "created_at": online_entry.created_at if online_entry.created_at else datetime.now(),
            "queue_time": entry_time,
        })


def _process_legacy_appointments(
    db: Session,
    appointments: list,
    queues_by_specialty: dict,
    seen_appointment_ids: set,
    today: date,
) -> None:
    """R-22 Phase 3: Process legacy Appointment records into specialty queues."""
    from app.models.service import Service
    from app.models.visit import Visit

    for appointment in appointments:
        if appointment.id in seen_appointment_ids:
            continue
        seen_appointment_ids.add(appointment.id)

        specialty = None
        appointment_date = getattr(appointment, 'appointment_date', today)
        patient_id = getattr(appointment, 'patient_id', None)

        if hasattr(appointment, 'services') and appointment.services:
            for service_item in appointment.services:
                service = None
                if isinstance(service_item, dict):
                    service_id = service_item.get('id')
                    if service_id:
                        service = db.query(Service).filter(Service.id == service_id).first()
                elif isinstance(service_item, int):
                    service = db.query(Service).filter(Service.id == service_item).first()
                elif isinstance(service_item, str):
                    service = db.query(Service).filter(Service.name == service_item).first()
                if service and service.department_key:
                    specialty = service.department_key
                    break

        if not specialty:
            specialty = getattr(appointment, 'department', None) or "general"

        visit_exists = False
        doctor_id = getattr(appointment, 'doctor_id', None)
        if patient_id and appointment_date:
            try:
                visit_filters = [
                    Visit.patient_id == patient_id,
                    Visit.visit_date == appointment_date,
                ]
                if doctor_id is not None:
                    visit_filters.append(Visit.doctor_id == doctor_id)
                else:
                    visit_filters.append(Visit.doctor_id.is_(None))
                existing_visit = db.query(Visit).filter(and_(*visit_filters)).first()
                if existing_visit:
                    visit_exists = True
            except Exception:
                pass

        if visit_exists:
            continue

        _ensure_specialty_queue(queues_by_specialty, specialty, doctor_id)

        appointment_queue_time = None
        try:
            if patient_id and appointment_date and doctor_id is not None:
                queue_entry_row = db.execute(
                    text("""
                        SELECT qe.queue_time
                        FROM queue_entries qe
                        JOIN daily_queues dq ON qe.queue_id = dq.id
                        WHERE qe.patient_id = :patient_id
                          AND qe.visit_id IS NULL
                          AND dq.day = :appointment_date
                          AND dq.specialist_id = :doctor_id
                        ORDER BY qe.created_at DESC
                        LIMIT 1
                    """),
                    {
                        "patient_id": patient_id,
                        "appointment_date": appointment_date,
                        "doctor_id": doctor_id,
                    },
                ).first()
                if queue_entry_row and queue_entry_row.queue_time:
                    appointment_queue_time = queue_entry_row.queue_time
        except Exception:
            pass

        queues_by_specialty[specialty]["entries"].append({
            "type": "appointment",
            "data": appointment,
            "created_at": appointment.created_at,
            "queue_time": appointment_queue_time,
        })

        if not queues_by_specialty[specialty]["doctor"]:
            appointment_doctor = getattr(appointment, 'doctor', None)
            if appointment_doctor:
                queues_by_specialty[specialty]["doctor"] = appointment_doctor



# ===================== R-22 Phase 4: Entry serialization + queue payload =====================


def _serialize_queue_entry(
    *,
    entry_type: str,
    record_id: int | None,
    source: str,
    appointment_id_value: int | None,
    entry_visit_id: int | None,
    queue_entry_number: int,
    patient_id: int | None,
    patient_name: str,
    patient_birth_year: int | None,
    phone: str,
    address: str | None,
    services: list,
    service_codes: list,
    service_details: list,
    entry_wrapper: dict,
    total_cost: float | int,
    payment_status: str | None,
    payment_type: str | None,
    available_actions: list,
    canonical_status: str,
    entry_queue_time: Any,
    entry_updated_at: Any,
    entry_display_time_kind: str,
    visit_time: str | None,
    discount_mode: str,
    entry_data: Any,
    latest_lab_report: dict | None,
    entry_department_key: str | None,
    entry_department: str | None,
) -> dict:
    """R-22 Phase 4: Serialize a single queue entry into the API response dict."""
    can_mark_paid = "mark_paid" in available_actions
    can_start_visit = "start_visit" in available_actions
    can_print_ticket = "print_ticket" in available_actions
    can_complete = "complete" in available_actions
    can_cancel = "cancel" in available_actions
    can_view_emr = "view_emr" in available_actions
    can_schedule_next = "schedule_next" in available_actions

    return {
        "id": record_id,
        "canonical_record_id": record_id,
        "record_kind": entry_type,
        "source_kind": source,
        "appointment_id": appointment_id_value,
        "visit_id": entry_visit_id,
        "number": queue_entry_number,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "patient_birth_year": patient_birth_year,
        "phone": phone,
        "address": address,
        "services": services,
        "service_codes": service_codes,
        "service_details": service_details,
        "service_name": entry_wrapper.get("service_name"),
        "service_id": entry_wrapper.get("service_id"),
        "cost": total_cost,
        "payment_status": payment_status,
        "payment_type": payment_type,
        "can_mark_paid": can_mark_paid,
        "can_start_visit": can_start_visit,
        "can_print_ticket": can_print_ticket,
        "can_complete": can_complete,
        "can_cancel": can_cancel,
        "can_view_emr": can_view_emr,
        "can_schedule_next": can_schedule_next,
        "available_actions": available_actions,
        "source": source,
        "status": canonical_status,
        "canonical_status": canonical_status,
        "queue_status": canonical_status,
        "queue_position": queue_entry_number,
        "created_at": _serialize_registrar_datetime(entry_wrapper.get("created_at")),
        "queue_time": _serialize_registrar_datetime(entry_queue_time),
        "updated_at": _serialize_registrar_datetime(entry_updated_at),
        "last_changed_at": _serialize_registrar_datetime(entry_updated_at),
        "display_time_kind": entry_display_time_kind,
        "timezone": "Asia/Tashkent",
        "called_at": None,
        "visit_time": visit_time,
        "discount_mode": discount_mode,
        "approval_status": getattr(entry_data, "approval_status", None),
        "latest_lab_report": latest_lab_report,
        "type": entry_type,
        "record_type": entry_type,
        "queue_entry_id": entry_wrapper.get("queue_entry_id"),
        "department_key": entry_department_key,
        "department": entry_department,
        "session_id": getattr(entry_data, 'session_id', None),
    }


def _build_queue_payload(
    *,
    queue_data: dict,
    specialty: str,
    queue_number: int,
    entries: list,
) -> dict:
    """R-22 Phase 4: Build the final queue payload wrapper with stats."""
    return {
        "queue_id": queue_number,
        "specialist_id": queue_data["doctor_id"],
        "specialist_name": (
            queue_data["doctor"].user.full_name
            if queue_data.get("doctor") and queue_data["doctor"].user
            else f"Специалист #{queue_data['doctor_id']}"
        ),
        "specialty": specialty,
        "timezone": "Asia/Tashkent",
        "cabinet": queue_data["doctor"].cabinet if queue_data.get("doctor") else "N/A",
        "integrity_warnings": list(dict.fromkeys(queue_data.get("integrity_warnings", []))),
        "has_integrity_warnings": bool(queue_data.get("integrity_warnings")),
        "opened_at": datetime.now(UTC).isoformat(),
        "entries": entries,
        "stats": {
            "total": len(entries),
            "waiting": len([e for e in entries if e.get("status") == "waiting"]),
            "called": len([e for e in entries if e.get("status") == "called"]),
            "served": len([e for e in entries if e.get("status") == "served"]),
            "online_entries": len(
                [e for e in entries if e.get("source") == "online"]
            ),
        },
    }



# ===================== R-22 Phase 5: Queue entry lookup =====================


def _same_patient_queue_entry_for_visit_id(
    db: Session,
    visit_id: int | None,
    patient_id: int | None,
):
    """R-22 Phase 5: Find the OnlineQueueEntry linked to a visit by visit_id + patient_id.

    Returns None if either id is None or no entry is found.
    """
    from app.models.online_queue import OnlineQueueEntry
    if visit_id is None or patient_id is None:
        return None
    return (
        db.query(OnlineQueueEntry)
        .filter(
            OnlineQueueEntry.visit_id == visit_id,
            OnlineQueueEntry.patient_id == patient_id,
        )
        .order_by(OnlineQueueEntry.id.asc())
        .first()
    )


def _same_patient_queue_entry_for_visit(db: Session, visit):
    """R-22 Phase 5: Convenience wrapper around _same_patient_queue_entry_for_visit_id."""
    return _same_patient_queue_entry_for_visit_id(
        db,
        visit.id,
        visit.patient_id,
    )


def _resolve_queue_entry_metadata(
    *,
    db: Session,
    entry_type: str,
    entry_data: Any,
    entry_wrapper: dict,
    record_id: int | None,
    patient_id: int | None,
    appointment_date: Any,
    doctor_id: int | None,
    idx: int,
) -> tuple[int, Any, Any]:
    """R-22 Phase 5: Resolve (queue_entry_number, queue_entry_time, queue_entry_updated_at).

    Lookup priority depends on entry_type:
    - online_queue: read directly from OnlineQueueEntry (or entry_wrapper for QR-visits)
    - visit: lookup via _same_patient_queue_entry_for_visit_id
    - appointment: SQL query against queue_entries table (same patient + day + doctor)
    Falls back to (idx, None, None) on any error.
    """
    queue_entry_number = idx
    queue_entry_time = None
    queue_entry_updated_at = None

    if not record_id:
        return queue_entry_number, queue_entry_time, queue_entry_updated_at

    try:
        if entry_type == "online_queue":
            # entry_data may be Visit (for QR-visits) or OnlineQueueEntry
            is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')

            if is_visit_object:
                queue_entry_number = entry_wrapper.get("oqe_number") or idx
                queue_entry_time = entry_wrapper.get("oqe_queue_time")
                queue_entry_updated_at = entry_wrapper.get("oqe_updated_at")
            else:
                queue_entry_number = (
                    entry_data.number
                    if hasattr(entry_data, 'number') and entry_data.number is not None
                    else idx
                )
                queue_entry_time = (
                    entry_data.queue_time
                    if hasattr(entry_data, 'queue_time') and entry_data.queue_time
                    else None
                )
                queue_entry_updated_at = getattr(entry_data, 'updated_at', None)
        elif entry_type == "visit":
            queue_entry_row = _same_patient_queue_entry_for_visit_id(
                db,
                record_id,
                patient_id,
            )
            if queue_entry_row:
                queue_entry_number = queue_entry_row.number
                queue_entry_time = queue_entry_row.queue_time
                queue_entry_updated_at = queue_entry_row.updated_at
        elif (
            entry_type == "appointment"
            and patient_id
            and appointment_date
            and doctor_id is not None
        ):
            queue_entry_row = db.execute(
                text(
                    """
                    SELECT qe.number, qe.queue_time, qe.updated_at
                    FROM queue_entries qe
                    JOIN daily_queues dq ON qe.queue_id = dq.id
                    WHERE qe.patient_id = :patient_id
                      AND qe.visit_id IS NULL
                      AND dq.day = :appointment_date
                      AND dq.specialist_id = :doctor_id
                    ORDER BY qe.created_at DESC
                    LIMIT 1
                    """
                ),
                {
                    "patient_id": patient_id,
                    "appointment_date": appointment_date,
                    "doctor_id": doctor_id,
                },
            ).first()
            if queue_entry_row:
                queue_entry_number = queue_entry_row.number
                queue_entry_time = queue_entry_row.queue_time
                queue_entry_updated_at = queue_entry_row.updated_at
    except Exception as e:
        logger.debug(
            "get_today_queues: Ошибка получения queue_time: %s", str(e)
        )

    return queue_entry_number, queue_entry_time, queue_entry_updated_at



# ===================== R-22 Phase 6: Per-type entry processing =====================


_APPOINTMENT_STATUS_MAPPING = {
    "scheduled": "waiting",
    "pending": "waiting",
    "confirmed": "waiting",
    "paid": "waiting",
    "in_progress": "called",
    "in_visit": "called",
    "completed": "served",
    "cancelled": "no_show",
    "canceled": "no_show",
    "no_show": "no_show",
}


def _process_appointment_entry(
    *,
    db: Session,
    entry_data: Any,
    entry_wrapper: dict,
    today: date,
) -> dict | None:
    """R-22 Phase 6: Process an Appointment row into entry fields.

    Returns a dict with the populated fields, or None to signal "skip this entry"
    (caller should `continue` to the next iteration).
    """
    if entry_data is None:
        logger.warning("get_today_queues: appointment entry with None data, skipping")
        return None

    from app.models.patient import Patient

    appointment = entry_data
    record_id = appointment.id
    patient_id = appointment.patient_id
    appointment_date = getattr(appointment, 'appointment_date', today)
    doctor_id = getattr(appointment, 'doctor_id', None)
    visit_time = (
        str(appointment.appointment_time)
        if hasattr(appointment, 'appointment_time')
        else None
    )

    patient_name = "Неизвестный пациент"
    phone = "Не указан"
    patient_birth_year = None
    address = None

    patient = (
        db.query(Patient)
        .filter(Patient.id == appointment.patient_id)
        .first()
    )
    if patient:
        patient_name = patient.short_name()
        phone = patient.phone or "Не указан"
        if patient.birth_date:
            patient_birth_year = patient.birth_date.year
        address = patient.address
    else:
        logger.warning(
            "get_today_queues: Пациент не найден для Appointment ID=%d, patient_id=%s",
            appointment.id,
            appointment.patient_id,
        )
        patient_name = (
            f"Пациент ID={appointment.patient_id}"
            if appointment.patient_id
            else "Неизвестный пациент"
        )

    services: list = []
    service_codes: list = []
    if hasattr(appointment, 'services') and appointment.services:
        if isinstance(appointment.services, list):
            services = appointment.services
            for service in services:
                if isinstance(service, str):
                    if (
                        len(service) <= 10
                        or '-' in service
                        or service.isalnum()
                    ):
                        service_codes.append(service)

    total_cost = 0.0
    if (
        hasattr(appointment, 'payment_amount')
        and appointment.payment_amount
    ):
        total_cost = float(appointment.payment_amount)

    entry_status = _APPOINTMENT_STATUS_MAPPING.get(appointment.status, "waiting")
    discount_mode = _normalize_registration_discount_mode(
        getattr(appointment, "visit_type", None)
    )
    source = "desk"  # Appointment обычно создается регистратором

    try:
        entry_wrapper["visit_id"] = CanonicalVisitService(
            db
        ).resolve_canonical_visit(
            appointment.id,
            create_if_missing=False,
        )
    except CanonicalVisitResolutionError as exc:
        if exc.status_code != 404:
            logger.warning(
                "get_today_queues: failed to resolve canonical visit for appointment_id=%s: %s",
                appointment.id,
                exc.detail,
            )
        entry_wrapper["visit_id"] = None

    return {
        "record_id": record_id,
        "patient_id": patient_id,
        "appointment_date": appointment_date,
        "doctor_id": doctor_id,
        "visit_time": visit_time,
        "patient_name": patient_name,
        "phone": phone,
        "patient_birth_year": patient_birth_year,
        "address": address,
        "services": services,
        "service_codes": service_codes,
        "total_cost": total_cost,
        "entry_status": entry_status,
        "discount_mode": discount_mode,
        "source": source,
    }



def _process_online_queue_entry(
    *,
    db: Session,
    entry_data: Any,
    entry_wrapper: dict,
    specialty: str,
) -> dict | None:
    """R-22 Phase 7: Process an OnlineQueueEntry (or QR-Visit) into entry fields.

    Returns a dict with the populated fields, or None to signal "skip this entry"
    (caller should `continue` to the next iteration).
    Mutates `entry_wrapper` in place: sets queue_entry_id, visit_id, oqe_*, service_name, service_id, service_code.
    """
    if entry_data is None:
        logger.warning("get_today_queues: online_queue entry with None data, skipping")
        return None

    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.visit import VisitService
    from app.services.service_mapping import get_default_service_by_specialty

    # entry_data может быть OnlineQueueEntry или Visit (для QR-визитов)
    is_visit_object = hasattr(entry_data, 'visit_date') and not hasattr(entry_data, 'queue_id')

    services: list = []
    service_codes: list = []
    service_details: list = []

    if is_visit_object:
        # entry_data это Visit с source='online'
        visit = entry_data
        queue_entry_for_visit = _same_patient_queue_entry_for_visit(db, visit)
        if queue_entry_for_visit:
            record_id = queue_entry_for_visit.id
            entry_wrapper["oqe_number"] = queue_entry_for_visit.number
            entry_wrapper["oqe_total_amount"] = queue_entry_for_visit.total_amount or 0
            entry_wrapper["oqe_queue_time"] = queue_entry_for_visit.queue_time
            entry_wrapper["oqe_updated_at"] = queue_entry_for_visit.updated_at
        else:
            record_id = visit.id
        entry_wrapper["visit_id"] = visit.id
        entry_wrapper["queue_entry_id"] = queue_entry_for_visit.id if queue_entry_for_visit else None
        patient_id = visit.patient_id
        entry_status = visit.status or "waiting"
        source = visit.source or "online"
        discount_mode = visit.discount_mode or "none"
        visit_time = str(visit.visit_time) if hasattr(visit, 'visit_time') and visit.visit_time else None

        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        if patient:
            patient_name = patient.short_name()
            phone = patient.phone or "Не указан"
            patient_birth_year = patient.birth_date.year if patient.birth_date else None
            address = patient.address
        else:
            patient_name = "Неизвестный пациент"
            phone = "Не указан"
            patient_birth_year = None
            address = None

        # Услуги из VisitService
        visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        for vs in visit_services:
            svc = db.query(Service).filter(Service.id == vs.service_id).first()
            if svc:
                service_codes.append(svc.service_code or svc.code or "")
                services.append({
                    "service_id": svc.id,
                    "name": svc.name,
                    "code": svc.service_code or svc.code,
                    "price": float(vs.price) if vs.price else 0,
                    "quantity": vs.qty or 1,
                })
    else:
        # entry_data это OnlineQueueEntry (обычный случай)
        online_entry = entry_data
        record_id = online_entry.id
        entry_wrapper["queue_entry_id"] = online_entry.id
        patient_id = online_entry.patient_id
        patient_name = online_entry.patient_name or "Неизвестный пациент"
        phone = online_entry.phone or "Не указан"
        patient_birth_year = online_entry.birth_year
        address = online_entry.address
        entry_status = online_entry.status
        source = online_entry.source or "online"
        discount_mode = online_entry.discount_mode or "none"
        visit_time = None

        # Услуги из online_entry.services (list или JSON string)
        if hasattr(online_entry, 'services') and online_entry.services:
            if isinstance(online_entry.services, list):
                services = online_entry.services
                for service in services:
                    if isinstance(service, dict):
                        if service.get("code"):
                            service_codes.append(service["code"])
                        elif service.get("service_code"):
                            service_codes.append(service["service_code"])
                    elif isinstance(service, str):
                        service_codes.append(service)
            elif isinstance(online_entry.services, str):
                import json
                try:
                    services = json.loads(online_entry.services)
                    if isinstance(services, list):
                        for service in services:
                            if isinstance(service, dict) and service.get("code"):
                                service_codes.append(service["code"])
                except Exception:
                    pass

    # service_name: приоритет — имя из первой услуги, затем SSOT lookup по specialty
    service_name = None
    if services and len(services) > 0:
        first = services[0]
        if isinstance(first, dict):
            service_name = first.get("name") or first.get("service_name")
        elif isinstance(first, str):
            service_name = first

    if not service_name:
        default_service = get_default_service_by_specialty(db, specialty)
        if default_service:
            service_name = default_service["name"]
            entry_wrapper["service_id"] = default_service["id"]
            entry_wrapper["service_code"] = default_service["service_code"]

    entry_wrapper["service_name"] = service_name

    # service_codes из entry_data.service_codes (дополнительно)
    if hasattr(entry_data, 'service_codes') and entry_data.service_codes:
        if isinstance(entry_data.service_codes, list):
            service_codes.extend(entry_data.service_codes)
        elif isinstance(entry_data.service_codes, str):
            import json
            try:
                parsed = json.loads(entry_data.service_codes)
                if isinstance(parsed, list):
                    service_codes.extend(parsed)
            except Exception:
                pass

    # total_cost: приоритет oqe_total_amount > entry_data.total_amount > VisitService SUM
    total_cost = entry_wrapper.get("oqe_total_amount") or getattr(entry_data, 'total_amount', 0) or 0
    if total_cost == 0:
        linked_visit_id = getattr(entry_data, 'visit_id', None) or entry_wrapper.get("visit_id")
        if linked_visit_id:
            try:
                cost_row = db.execute(
                    text("SELECT SUM(price * qty) as total FROM visit_services WHERE visit_id = :vid"),
                    {"vid": linked_visit_id}
                ).first()
                if cost_row and cost_row.total:
                    total_cost = float(cost_row.total)
            except Exception:
                pass  # Fallback на 0

    # service_details из entry_data.services
    if hasattr(entry_data, 'services') and entry_data.services:
        parsed_services = entry_data.services
        if isinstance(parsed_services, str):
            import json
            try:
                parsed_services = json.loads(parsed_services)
            except Exception:
                parsed_services = []

        if isinstance(parsed_services, list):
            for svc in parsed_services:
                if isinstance(svc, dict):
                    service_details.append({
                        "id": svc.get("id") or svc.get("service_id"),
                        "code": svc.get("code") or svc.get("service_code"),
                        "name": svc.get("name") or svc.get("service_name"),
                        "price": float(svc.get("price", 0)) if svc.get("price") else 0,
                    })
                elif isinstance(svc, str):
                    service_details.append({
                        "id": None,
                        "code": None,
                        "name": svc,
                        "price": 0,
                    })

    return {
        "record_id": record_id,
        "patient_id": patient_id,
        "patient_name": patient_name,
        "phone": phone,
        "patient_birth_year": patient_birth_year,
        "address": address,
        "entry_status": entry_status,
        "source": source,
        "discount_mode": discount_mode,
        "visit_time": visit_time,
        "services": services,
        "service_codes": service_codes,
        "service_details": service_details,
        "total_cost": total_cost,
    }



_VISIT_STATUS_MAPPING = {
    "confirmed": "waiting",
    "pending_confirmation": "waiting",
    "in_progress": "called",
    "completed": "served",
    "cancelled": "no_show",
    "canceled": "no_show",
    "no_show": "no_show",
}


def _process_visit_entry(
    *,
    db: Session,
    entry_data: Any,
    entry_wrapper: dict,
    specialty: str,
) -> dict | None:
    """R-22 Phase 8: Process a Visit row into entry fields.

    Returns a dict with the populated fields, or None to signal "skip this entry"
    (caller should `continue` to the next iteration). Skipping happens when:
    - entry_data is None
    - ecg_only flag set but no ECG services found
    - non-ECG filter and visit has only ECG services
    """
    if entry_data is None:
        logger.warning("get_today_queues: visit entry with None data, skipping")
        return None

    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.visit import VisitService
    from app.services.service_mapping import get_service_code

    visit = entry_data
    record_id = visit.id
    patient_id = visit.patient_id
    visit_time = visit.visit_time
    discount_mode = visit.discount_mode

    patient_name = "Неизвестный пациент"
    phone = "Не указан"
    patient_birth_year = None
    address = None

    patient = (
        db.query(Patient).filter(Patient.id == visit.patient_id).first()
    )
    if patient:
        patient_name = patient.short_name()
        phone = patient.phone or "Не указан"
        if patient.birth_date:
            patient_birth_year = patient.birth_date.year
        address = patient.address
    else:
        logger.warning(
            "get_today_queues: Пациент не найден для Visit ID=%d, patient_id=%s",
            visit.id,
            visit.patient_id,
        )
        patient_name = (
            f"Пациент ID={visit.patient_id}"
            if visit.patient_id
            else "Неизвестный пациент"
        )

    all_visit_services = (
        db.query(VisitService)
        .filter(VisitService.visit_id == visit.id)
        .all()
    )

    ecg_only_flag = entry_wrapper.get("ecg_only", False)
    filter_services_flag = entry_wrapper.get("filter_services", False)

    visit_services = []
    if filter_services_flag or ecg_only_flag:
        # Показываем только ЭКГ услуги (для очереди echokg)
        for vs in all_visit_services:
            if hasattr(vs, 'service_id') and vs.service_id:
                service = (
                    db.query(Service)
                    .filter(Service.id == vs.service_id)
                    .first()
                )
                if service and service.queue_tag == 'ecg':
                    visit_services.append(vs)
        if not visit_services:
            logger.warning(
                "get_today_queues: Флаг ecg_only=True, но ЭКГ услуг не найдено для Visit %d",
                visit.id,
            )
            return None
    else:
        # Исключаем ЭКГ услуги (для очереди cardiology)
        for vs in all_visit_services:
            if hasattr(vs, 'service_id') and vs.service_id:
                service = (
                    db.query(Service)
                    .filter(Service.id == vs.service_id)
                    .first()
                )
                if service and service.queue_tag != 'ecg':
                    visit_services.append(vs)
        if not visit_services:
            logger.debug(
                "get_today_queues: Пропущен Visit %d для specialty=%s: содержит только ЭКГ услуги",
                visit.id,
                specialty,
            )
            return None

    # Fallback на все услуги если фильтр пустой
    if not visit_services:
        visit_services = all_visit_services

    services: list = []
    service_codes: list = []
    service_details: list = []
    total_cost = 0.0

    for vs in visit_services:
        service_code_to_use = None
        svc = None
        if hasattr(vs, 'service_id') and vs.service_id:
            svc = (
                db.query(Service)
                .filter(Service.id == vs.service_id)
                .first()
            )
            if svc:
                service_code_to_use = get_service_code(
                    {
                        'service_code': getattr(svc, 'service_code', None),
                    }
                )

        if service_code_to_use:
            services.append(service_code_to_use)
            service_codes.append(service_code_to_use)
        elif vs.name:
            services.append(vs.name)

        if svc:
            service_details.append({
                "id": svc.id,
                "code": service_code_to_use or svc.code,
                "name": svc.name,
                "price": float(svc.price) if svc.price else 0,
            })

        if vs.price:
            total_cost += float(vs.price) * (vs.qty or 1)

    source = getattr(visit, 'source', None) or 'desk'
    entry_status = _VISIT_STATUS_MAPPING.get(visit.status, "waiting")
    discount_mode = _normalize_registration_discount_mode(
        getattr(visit, "discount_mode", None)
    )
    visit_department = getattr(visit, 'department', None)

    return {
        "record_id": record_id,
        "patient_id": patient_id,
        "visit_time": visit_time,
        "patient_name": patient_name,
        "phone": phone,
        "patient_birth_year": patient_birth_year,
        "address": address,
        "services": services,
        "service_codes": service_codes,
        "service_details": service_details,
        "total_cost": total_cost,
        "entry_status": entry_status,
        "discount_mode": discount_mode,
        "source": source,
        "visit_department": visit_department,
    }



# ===================== ТЕКУЩИЕ ОЧЕРЕДИ =====================


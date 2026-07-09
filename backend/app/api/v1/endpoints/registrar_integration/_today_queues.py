from __future__ import annotations

from typing import Any

from app.api.v1.endpoints.registrar_integration._helpers import *  # noqa

from app.api.v1.endpoints.registrar_integration._helpers import (
    _latest_lab_report_summaries_by_visit,
    _normalize_queue_status_for_registrar,
    _registrar_available_actions,
    _resolve_payment_truth,
)  # noqa: F401


from app.api.v1.endpoints.registrar_integration._queue_ops import (  # noqa: F401
    _build_queue_payload,
    _detect_ecg_services,
    _ensure_specialty_queue,
    _get_visit_created_at,
    _get_visit_queue_time,
    _load_queue_data_for_date,
    _normalize_department_filter,
    _parse_queue_target_date,
    _process_appointment_entry,
    _process_legacy_appointments,
    _process_online_queue_entries,
    _process_online_queue_entry,
    _process_visit_entry,
    _resolve_queue_entry_metadata,
    _same_patient_queue_entry_for_visit,
    _serialize_queue_entry,
)

def _resolve_entry_department(
    db: Session,
    entry_type: str,
    entry_data,
    record_id,
    visit_department,
):
    """Resolve department_key and department for a queue entry.

    For visit entries: uses visit_department + VisitService → Service.department_key.
    For appointment entries: uses appointment.services → Service.department_key.
    Returns (entry_department_key, entry_department).
    """
    from app.models.service import Service
    from app.models.visit import VisitService

    # [OK] ДОБАВЛЯЕМ department_key и department для фронтенда
    entry_department_key = None
    entry_department = None
    if entry_type == "visit":
        # Для Visit используем department, который был сохранен выше
        entry_department = visit_department

        # Для Visit получаем department_key из услуг
        from app.models.visit import VisitService

        visit_services_for_dept = (
            db.query(VisitService)
            .filter(VisitService.visit_id == record_id)
            .all()
        )
        for vs in visit_services_for_dept:
            if vs.service_id:
                svc = (
                    db.query(Service)
                    .filter(Service.id == vs.service_id)
                    .first()
                )
                if svc and svc.department_key:
                    entry_department_key = svc.department_key
                    break
    elif entry_type == "appointment":
        if entry_data is None:
            logger.warning("get_today_queues: appointment entry with None data, skipping")
            return None, None
        # Для Appointment получаем из услуг или напрямую
        appointment_obj = entry_data
        if (
            hasattr(appointment_obj, 'services')
            and appointment_obj.services
        ):
            for service_item in appointment_obj.services:
                svc = None
                if isinstance(service_item, dict):
                    service_id = service_item.get('id')
                    if service_id:
                        svc = (
                            db.query(Service)
                            .filter(Service.id == service_id)
                            .first()
                        )
                elif isinstance(service_item, int):
                    svc = (
                        db.query(Service)
                        .filter(Service.id == service_item)
                        .first()
                    )
                elif isinstance(service_item, str):
                    # [OK] ДОБАВЛЕНО: Поиск услуги по названию (Appointment.services - это JSON строк)
                    svc = (
                        db.query(Service)
                        .filter(Service.name == service_item)
                        .first()
                    )

                if svc and svc.department_key:
                    entry_department_key = svc.department_key
                    break

    return entry_department_key, entry_department


def _process_visits_for_queues(
    db: Session,
    visits: list,
    today,
    queues_by_specialty: dict,
    seen_visit_ids: set,
):
    """Process Visit records and append them to queues_by_specialty.

    Handles ECG service detection and split logic:
    - Visits with both ECG and non-ECG services are split into echokg + cardiology.
    - Visits with only ECG go to echokg.
    - Other visits go to specialty from service.department_key or visit.department.
    """
    from app.models.service import Service
    from app.models.visit import VisitService

    for visit in visits:
        # Пропускаем если уже обработан
        if visit.id in seen_visit_ids:
            continue
        # ⚠️ НЕ добавляем в seen_visit_ids здесь - сначала проверяем OQE

        # ⭐ PHASE 1.1: Пропускаем Visit если есть связанный OnlineQueueEntry
        # Очередь должна читаться ТОЛЬКО из OnlineQueueEntry (SSOT)
        has_queue_entry = _same_patient_queue_entry_for_visit(db, visit)
        if has_queue_entry:
            # ⚠️ НЕ добавляем в seen_visit_ids - пусть OQE обрабатывается
            logger.debug(
                "get_today_queues: PHASE 1.1 - Visit %d пропущен, есть OnlineQueueEntry",
                visit.id,
            )
            continue

        # ✅ Только Visit БЕЗ OQE добавляем в seen_visit_ids
        seen_visit_ids.add(visit.id)

        # [OK] Определяем specialty на основе услуг визита, а не только department
        # Проверяем услуги визита для правильного определения очереди
        from app.models.service import Service
        from app.models.visit import VisitService

        visit_services = (
            db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        )
        service_ids = [vs.service_id for vs in visit_services]
        services = (
            db.query(Service).filter(Service.id.in_(service_ids)).all()
            if service_ids
            else []
        )

        # R-22: ECG detection extracted to helper
        has_ecg, ecg_services_count, non_ecg_services_count = _detect_ecg_services(services)

        # Только ЭКГ: если есть ЭКГ услуги и нет не-ЭКГ услуг
        has_only_ecg = has_ecg and non_ecg_services_count == 0
        logger.debug(
            "get_today_queues: Итог для Visit %d: has_ecg=%s, has_only_ecg=%s, ЭКГ услуг=%d, не-ЭКГ услуг=%d",
            visit.id,
            has_ecg,
            has_only_ecg,
            ecg_services_count,
            non_ecg_services_count,
        )

        # [OK] Определяем specialty: если есть ЭКГ, разделяем на отдельные очереди
        visit_date = visit.visit_date or today  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
        patient_id = visit.patient_id

        if has_ecg and not has_only_ecg:
            # Визит содержит и ЭКГ и другие услуги - разделяем:
            # 1. Создаем запись для ЭКГ в очередь echokg (только ЭКГ услуги)
            specialty_ecg = "echokg"
            # R-22: ensure ECG queue exists
            _ensure_specialty_queue(queues_by_specialty, specialty_ecg, visit.doctor_id)

            # R-22: created_at extraction moved to helper
            visit_created_at = _get_visit_created_at(visit)

            # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
            # R-22: queue_time extraction moved to helper
            visit_queue_time = _get_visit_queue_time(db, visit)

            queues_by_specialty[specialty_ecg]["entries"].append(
                {
                    "type": "visit",
                    "data": visit,
                    "created_at": visit_created_at,
                    "queue_time": visit_queue_time,  # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
                    "filter_services": True,  # Флаг для фильтрации услуг при обработке
                    "ecg_only": True,  # Только ЭКГ услуги для этой записи
                }
            )

            # 2. Создаем запись для кардиолога в очередь cardiology (без ЭКГ услуг)
            specialty = "cardiology"
            # R-22: ensure queue exists
            _ensure_specialty_queue(queues_by_specialty, specialty, visit.doctor_id)
            # R-22: created_at extraction moved to helper
            visit_created_at = _get_visit_created_at(visit)

            # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
            # R-22: queue_time extraction moved to helper
            visit_queue_time = _get_visit_queue_time(db, visit)

            queues_by_specialty[specialty]["entries"].append(
                {
                    "type": "visit",
                    "data": visit,
                    "created_at": visit_created_at,
                    "queue_time": visit_queue_time,  # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
                    "filter_services": True,  # Флаг для фильтрации услуг при обработке
                    "ecg_only": False,  # Исключаем ЭКГ услуги
                }
            )
            continue  # Переходим к следующему визиту
        elif has_ecg and has_only_ecg:
            # Только ЭКГ - идёт в echokg
            specialty = "echokg"

            # R-22: ensure queue exists
            _ensure_specialty_queue(queues_by_specialty, specialty, visit.doctor_id)

            # R-22: created_at extraction moved to helper
            visit_created_at = _get_visit_created_at(visit)

            # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
            # R-22: queue_time extraction moved to helper
            visit_queue_time = _get_visit_queue_time(db, visit)

            queues_by_specialty[specialty]["entries"].append(
                {
                    "type": "visit",
                    "data": visit,
                    "created_at": visit_created_at,
                    "queue_time": visit_queue_time,  # ✅ ИСПРАВЛЕНО: Добавляем queue_time для правильной сортировки
                    "filter_services": True,  # [OK] ИСПРАВЛЕНО: Включаем фильтрацию услуг
                    "ecg_only": True,  # [OK] ИСПРАВЛЕНО: Показываем только ЭКГ услуги
                }
            )
            continue  # Переходим к следующему визиту
        else:
            # [OK] ОБНОВЛЕНО: Определяем specialty по department_key из услуг визита
            # Приоритет: service.department_key > visit.department > "general"
            specialty = None

            # Проверяем department_key из услуг
            for service in services:
                if service.department_key:
                    specialty = service.department_key
                    break

            # Fallback на visit.department
            if not specialty:
                specialty = visit.department or "general"

        if specialty not in queues_by_specialty:
            queues_by_specialty[specialty] = {
                "entries": [],
                "doctor": None,
                "doctor_id": visit.doctor_id,
            }

        # Безопасно получаем дату создания
        # [OK] УПРОЩЕНО: Используем getattr вместо try/except (Single Source of Truth)
        visit_created_at = getattr(visit, 'confirmed_at', None) or getattr(
            visit, 'created_at', None
        )

        # ✅ ИСПРАВЛЕНО: Получаем queue_time из связанной записи в queue_entries
        visit_queue_time = None
        try:
            queue_entry_row = _same_patient_queue_entry_for_visit(db, visit)
            if queue_entry_row and queue_entry_row.queue_time:
                visit_queue_time = queue_entry_row.queue_time
        except Exception:
            pass  # Тихая ошибка - используем created_at как fallback

        # ⭐ PHASE 1.2: Visit без OQE всегда type='visit'
        # Visit с source='online' уже пропущен выше (имеет OnlineQueueEntry)

        queues_by_specialty[specialty]["entries"].append(
            {
                "type": "visit",  # ✅ PHASE 1.2: Всегда 'visit' для Visit без OQE
                "data": visit,
                "created_at": visit_created_at,
                "queue_time": visit_queue_time,
            }
        )

        # [OK] УПРОЩЕНО: Используем getattr вместо try/except (Single Source of Truth)
        # ✅ ИСПРАВЛЕНО: Для visit записей обновляем doctor_id только если doctor ещё не установлен
        # Это предотвращает перезапись doctor_id, установленного online_queue записями
        if not queues_by_specialty[specialty]["doctor"]:
            visit_doctor = getattr(visit, 'doctor', None)
            if visit_doctor:
                queues_by_specialty[specialty]["doctor"] = visit_doctor
                # ✅ ИСПРАВЛЕНО: Обновляем doctor_id, если doctor найден
                queues_by_specialty[specialty]["doctor_id"] = visit_doctor.id
        # ✅ ИСПРАВЛЕНО: Убрана логика обновления doctor_id для visit записей, если specialty уже существует
        # Это предотвращает перезапись doctor_id, установленного online_queue записями (которые обрабатываются позже)



def _collect_lab_report_summaries(
    db: Session,
    queues_by_specialty: dict,
    department_filter,
):
    """Collect lab report summaries for visible entries.

    Returns (latest_lab_reports_by_visit: dict, include_lab_report_summary: bool).
    """
    include_lab_report_summary = bool(
        department_filter and department_filter.intersection({"lab", "laboratory"})
    )
    visible_entry_wrappers = []
    if include_lab_report_summary:
        for specialty, data in queues_by_specialty.items():
            specialty_key = str(specialty or "").strip().lower()
            if department_filter and specialty_key not in department_filter:
                continue
            visible_entry_wrappers.extend(data["entries"])

    visible_visit_ids: set[int] = set()
    for entry_wrapper in visible_entry_wrappers:
        entry_type = entry_wrapper.get("type")
        entry_data = entry_wrapper.get("data")
        entry_visit_id = (
            entry_wrapper.get("visit_id")
            or getattr(entry_data, "visit_id", None)
            or (
                getattr(entry_data, "id", None)
                if entry_type == "visit"
                else None
            )
        )
        if entry_visit_id:
            visible_visit_ids.add(entry_visit_id)

    latest_lab_reports_by_visit = _latest_lab_report_summaries_by_visit(
        db,
        visible_visit_ids,
    )
    return latest_lab_reports_by_visit, include_lab_report_summary


def _build_queue_result(
    db: Session,
    current_user,
    queues_by_specialty: dict,
    department_filter,
    today,
):
    """Build the final result list from queues_by_specialty.

    Processes each specialty queue: sorts entries, serializes each entry
    (visit/appointment/online_queue), resolves department/payment/status,
    and constructs the queue payload.

    Returns the result list.
    """
    from datetime import datetime

    result = []
    queue_number = 1
    seen_entry_keys = set()
    latest_lab_reports_by_visit, include_lab_report_summary = (
        _collect_lab_report_summaries(
            db=db,
            queues_by_specialty=queues_by_specialty,
            department_filter=department_filter,
        )
    )


    for specialty, queue_data in queues_by_specialty.items():
        specialty_key = str(specialty or "").strip().lower()
        if department_filter and specialty_key not in department_filter:
            continue

        entries_list = queue_data.get("entries", [])
        if not entries_list:
            continue

        # Сортируем записи по queue_time, затем по created_at
        entries_list.sort(
            key=lambda e: (
                e.get("queue_time") or e.get("created_at") or datetime.max,
                e.get("data").id if hasattr(e.get("data"), "id") else 0,
            )
        )

        # R-22 fix: separate output list to avoid in-place mutation during iteration
        entries = []
        for idx, entry in enumerate(entries_list):
            entry_type = entry.get("type")
            entry_data = entry.get("data")
            entry_id_val = getattr(entry_data, "id", "")
            entry_key = f"{entry_type}_{entry_id_val}"
            # R-22 fix: entry_wrapper is alias for entry (used in result serialization)
            entry_wrapper = entry
            # Пропускаем дубликаты
            if entry_key in seen_entry_keys:
                logger.debug(
                    "get_today_queues: Пропущен дубликат: %s (тип: %s)",
                    entry_key,
                    entry_type,
                )
                continue

            seen_entry_keys.add(entry_key)

            # Инициализируем общие переменные
            patient_id = None
            patient_name = "Неизвестный пациент"
            phone = "Не указан"
            patient_birth_year = None
            address = None
            services = []
            service_codes = []
            service_details = []  # ✅ НОВОЕ: Полные данные услуг для редактирования
            total_cost = 0
            source = "desk"
            entry_status = "waiting"
            visit_time = None
            discount_mode = "none"
            record_id = None
            visit_department = (
                None  # ✅ ДОБАВЛЕНО: для хранения department из Visit
            )
            appointment_date = None  # R-22 fix: для queue_entry lookup
            doctor_id = None  # R-22 fix: для queue_entry lookup

            if entry_type == "visit":
                # R-22 Phase 8: visit processing extracted to helper
                _vis = _process_visit_entry(
                    db=db,
                    entry_data=entry_data,
                    entry_wrapper=entry_wrapper,
                    specialty=specialty,
                )
                if _vis is None:
                    continue
                record_id = _vis["record_id"]
                patient_id = _vis["patient_id"]
                visit_time = _vis["visit_time"]
                patient_name = _vis["patient_name"]
                phone = _vis["phone"]
                patient_birth_year = _vis["patient_birth_year"]
                address = _vis["address"]
                services = _vis["services"]
                service_codes = _vis["service_codes"]
                service_details = _vis["service_details"]
                total_cost = _vis["total_cost"]
                entry_status = _vis["entry_status"]
                discount_mode = _vis["discount_mode"]
                source = _vis["source"]
                visit_department = _vis["visit_department"]

            elif entry_type == "appointment":
                # R-22 Phase 6: appointment processing extracted to helper
                _appt = _process_appointment_entry(
                    db=db,
                    entry_data=entry_data,
                    entry_wrapper=entry_wrapper,
                    today=today,
                )
                if _appt is None:
                    continue
                record_id = _appt["record_id"]
                patient_id = _appt["patient_id"]
                appointment_date = _appt["appointment_date"]
                doctor_id = _appt["doctor_id"]
                visit_time = _appt["visit_time"]
                patient_name = _appt["patient_name"]
                phone = _appt["phone"]
                patient_birth_year = _appt["patient_birth_year"]
                address = _appt["address"]
                services = _appt["services"]
                service_codes = _appt["service_codes"]
                total_cost = _appt["total_cost"]
                entry_status = _appt["entry_status"]
                discount_mode = _appt["discount_mode"]
                source = _appt["source"]

            elif entry_type == "online_queue":
                # R-22 Phase 7: online_queue processing extracted to helper
                _oqe = _process_online_queue_entry(
                    db=db,
                    entry_data=entry_data,
                    entry_wrapper=entry_wrapper,
                    specialty=specialty,
                )
                if _oqe is None:
                    continue
                record_id = _oqe["record_id"]
                patient_id = _oqe["patient_id"]
                patient_name = _oqe["patient_name"]
                phone = _oqe["phone"]
                patient_birth_year = _oqe["patient_birth_year"]
                address = _oqe["address"]
                entry_status = _oqe["entry_status"]
                source = _oqe["source"]
                discount_mode = _oqe["discount_mode"]
                visit_time = _oqe["visit_time"]
                services = _oqe["services"]
                service_codes = _oqe["service_codes"]
                service_details = _oqe["service_details"]
                total_cost = _oqe["total_cost"]

            # appointment_id must mean a real Appointment.id for this row.
            # Visit rows do not have an explicit Appointment FK, so a fuzzy
            # patient/date/doctor match can expose an unrelated appointment.
            appointment_id_value = record_id if entry_type == "appointment" else None

            # R-22 Phase 5: queue entry metadata lookup extracted to helper
            queue_entry_number, queue_entry_time, queue_entry_updated_at = _resolve_queue_entry_metadata(
                db=db,
                entry_type=entry_type,
                entry_data=entry_data,
                entry_wrapper=entry_wrapper,
                record_id=record_id,
                patient_id=patient_id,
                appointment_date=appointment_date,
                doctor_id=doctor_id,
                idx=idx,
            )

            # [OK] ДОБАВЛЯЕМ department_key и department для фронтенда
            entry_department_key, entry_department = _resolve_entry_department(
                db=db,
                entry_type=entry_type,
                entry_data=entry_data,
                record_id=record_id,
                visit_department=visit_department,
            )

            # ✅ ИСПРАВЛЕНО: Определяем queue_time для ответа (приоритет: из queue_entries > из entry_wrapper > created_at)
            entry_queue_time = queue_entry_time
            if not entry_queue_time and entry_wrapper.get("queue_time"):
                entry_queue_time = entry_wrapper["queue_time"]
            if not entry_queue_time:
                entry_queue_time = entry_wrapper.get("created_at")
            entry_updated_at = (
                queue_entry_updated_at
                or entry_wrapper.get("oqe_updated_at")
                or getattr(entry_data, "updated_at", None)
                or entry_wrapper.get("created_at")
            )
            entry_display_time_kind = (
                "queue_time" if queue_entry_time or entry_wrapper.get("queue_time") else "created_at"
            )

            entry_visit_id = (
                entry_wrapper.get("visit_id")
                or getattr(entry_data, "visit_id", None)
                or (record_id if entry_type == "visit" else None)
            )
            latest_lab_report = (
                latest_lab_reports_by_visit.get(entry_visit_id)
                if entry_visit_id
                else None
            )
            payment_status, payment_type = _resolve_payment_truth(
                db,
                visit_id=entry_visit_id,
                legacy_paid_at=getattr(entry_data, "payment_processed_at", None),
            )
            canonical_status = _normalize_queue_status_for_registrar(entry_status)
            available_actions = _registrar_available_actions(
                user=current_user,
                payment_status=payment_status,
                queue_status=canonical_status,
                visit_id=entry_visit_id,
                patient_id=patient_id,
            )
            # R-22 Phase 4: entry serialization extracted to helper
            # (can_* flags are computed inside _serialize_queue_entry)
            entries.append(
                _serialize_queue_entry(
                    entry_type=entry_type,
                    record_id=record_id,
                    source=source,
                    appointment_id_value=appointment_id_value,
                    entry_visit_id=entry_visit_id,
                    queue_entry_number=queue_entry_number,
                    patient_id=patient_id,
                    patient_name=patient_name,
                    patient_birth_year=patient_birth_year,
                    phone=phone,
                    address=address,
                    services=services,
                    service_codes=service_codes,
                    service_details=service_details,
                    entry_wrapper=entry_wrapper,
                    total_cost=total_cost,
                    payment_status=payment_status,
                    payment_type=payment_type,
                    available_actions=available_actions,
                    canonical_status=canonical_status,
                    entry_queue_time=entry_queue_time,
                    entry_updated_at=entry_updated_at,
                    entry_display_time_kind=entry_display_time_kind,
                    visit_time=visit_time,
                    discount_mode=discount_mode,
                    entry_data=entry_data,
                    latest_lab_report=latest_lab_report,
                    entry_department_key=entry_department_key,
                    entry_department=entry_department,
                )
            )

        # R-22 Phase 4: queue payload construction extracted to helper
        queue_data = _build_queue_payload(
            queue_data=queue_data,
            specialty=specialty,
            queue_number=queue_number,
            entries=entries,
        )

        result.append(queue_data)
        queue_number += 1

    return result


@router.get("/registrar/queues/today", response_model=dict[str, Any])
def get_today_queues(
    target_date: str | None = Query(
        None, description="Дата (YYYY-MM-DD), по умолчанию сегодня"
    ),
    department: str | None = Query(None, description="Фильтр по отделению"),
    db: Session = Depends(get_db),
    # [OK] ИСПРАВЛЕНО: Добавлена роль Cashier для доступа к очереди
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Registrar",
            "Cashier",
            "Doctor",
            "Lab",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """
    Получить все очереди на указанную дату для регистратуры
    Из detail.md стр. 363: GET /api/queue/today?specialist_id&date=YYYY-MM-DD

    ОБНОВЛЕНО: Теперь получаем данные из Visit вместо DailyQueue
    Доступ: Admin, Registrar, Cashier, Doctor, Lab, cardio, cardiology, derma, dentist

    Параметры:
    - target_date: дата в формате YYYY-MM-DD (опционально, по умолчанию - сегодня)
    - department: фильтр по отделению (опционально)
    """
    try:
        from datetime import datetime


        # R-22 Phase 5: _same_patient_queue_entry_for_visit_id and _same_patient_queue_entry_for_visit
        # promoted to module-level helpers (take db as first parameter).

        # R-22: date parsing + department filter extracted to helpers
        today = _parse_queue_target_date(target_date)
        department_filter = _normalize_department_filter(department)

        # R-22: data loading extracted to helper
        visits, appointments, online_entries = _load_queue_data_for_date(db, today)

        # Группируем записи по специальности
        queues_by_specialty = {}
        seen_visit_ids = set()  # Для отслеживания уже обработанных Visit
        seen_appointment_ids = set()  # Для отслеживания уже обработанных Appointment
        # Обрабатываем Visit (новая система)
        # Process Visit records into queues_by_specialty
        _process_visits_for_queues(
            db=db,
            visits=visits,
            today=today,
            queues_by_specialty=queues_by_specialty,
            seen_visit_ids=seen_visit_ids,
        )

        # R-22 Phase 3: online entries processing extracted to helper
        _process_online_queue_entries(db, online_entries, visits, queues_by_specialty, seen_visit_ids)

        # R-22 Phase 3: appointment processing extracted to helper
        _process_legacy_appointments(db, appointments, queues_by_specialty, seen_appointment_ids, today)

        # Формируем результат
        # Build the final result from queues_by_specialty
        result = _build_queue_result(
            db=db,
            current_user=current_user,
            queues_by_specialty=queues_by_specialty,
            department_filter=department_filter,
            today=today,
        )

        return {
            "queues": result,
            "total_queues": len(result),
            "date": today.isoformat(),
            "timezone": "Asia/Tashkent",
        }

    except Exception as e:
        logger.error(
            "get_today_queues: КРИТИЧЕСКАЯ ОШИБКА: %s: %s",
            type(e).__name__,
            e,
            exc_info=True,
        )
        logger.exception("Registrar operation failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== КАЛЕНДАРЬ ЗАПИСЕЙ =====================


@router.get("/registrar/calendar", response_model=dict[str, Any])
def get_registrar_calendar(
    start_date: date = Query(..., description="Начальная дата"),
    end_date: date = Query(..., description="Конечная дата"),
    doctor_id: int | None = Query(None, description="Фильтр по врачу"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Календарь записей для регистратуры
    Из detail.md стр. 174-181: календарь с цветовыми статусами
    """
    try:
        # Здесь будет логика получения записей из таблицы appointments/visits
        # Пока возвращаем заглушку

        return {
            "appointments": [],
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "status_colors": {
                "plan": "#6c757d",  # серый — план
                "confirmed": "#007bff",  # синий — подтверждено
                "queued": "#28a745",  # зеленый — в очереди
                "in_cabinet": "#fd7e14",  # оранжевый — в кабинете
                "done": "#20c997",  # зеленый тёмный — завершён
                "cancelled": "#dc3545",  # красный — отменен
                "no_show": "#dc3545",  # красный — неявка
            },
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== МАССОВОЕ СОЗДАНИЕ ОЧЕРЕДЕЙ =====================


# Pydantic schemas для batch endpoint
class BatchServiceItem(BaseModel):
    """Услуга для массового создания очередей"""

    specialist_id: int = Field(
        ..., description="ID специалиста (Doctor.id)"
    )
    service_id: int = Field(..., description="ID услуги")
    quantity: int = Field(default=1, ge=1, description="Количество")


class BatchQueueEntriesRequest(BaseModel):
    """Запрос на массовое создание записей в очереди"""

    patient_id: int = Field(..., description="ID пациента")
    source: str = Field(
        ...,
        description="Источник регистрации: 'online', 'desk', 'morning_assignment'",
        pattern="^(online|desk|morning_assignment)$",
    )
    services: list[BatchServiceItem] = Field(
        ..., min_length=1, description="Список услуг с указанием специалистов"
    )


class BatchQueueEntryResponse(BaseModel):
    """Ответ с информацией о созданной записи в очереди"""

    specialist_id: int
    queue_id: int
    number: int
    queue_time: str


class BatchQueueEntriesResponse(BaseModel):
    """Ответ на массовое создание очередей"""

    success: bool
    entries: list[BatchQueueEntryResponse]
    message: str


@router.post(
    "/registrar-integration/queue/entries/batch",
    response_model=BatchQueueEntriesResponse,
)
def create_queue_entries_batch(
    request: BatchQueueEntriesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Массовое создание записей в очереди (при добавлении новых услуг)

    Endpoint: POST /api/v1/registrar-integration/queue/entries/batch
    Из ONLINE_QUEUE_SYSTEM_IMPLEMENTATION.md стр. 271-306

    Use case: Регистратор редактирует существующую запись пациента и добавляет новые услуги.
    Для каждой новой услуги создается запись в соответствующей очереди специалиста.

    ВАЖНО:
    - Сохраняет оригинальный source из запроса (не меняет на "desk")
    - Устанавливает queue_time = текущее время (справедливое присвоение номера)
    - Проверяет дубликаты (пациент уже в очереди к специалисту на сегодня)
    - Использует SSOT queue_service.py для создания записей

    Требуемые роли: Admin, Registrar
    """
    import logging
    from zoneinfo import ZoneInfo

    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.patient import Patient

    logger = logging.getLogger(__name__)

    try:
        # Проверяем существование пациента
        patient = db.query(Patient).filter(Patient.id == request.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Пациент с ID {request.patient_id} не найден",
            )

        # Текущая дата и timezone
        timezone = ZoneInfo("Asia/Tashkent")
        today = date.today()
        current_time = datetime.now(timezone)

        # Группируем услуги по specialist_id (один врач = одна запись в очереди)
        services_by_specialist: dict[int, list[BatchServiceItem]] = {}
        for service_item in request.services:
            service = db.query(Service).filter(Service.id == service_item.service_id).first()
            if not service:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Услуга с ID {service_item.service_id} не найдена",
                )

            specialist_id = service_item.specialist_id

            from app.models.clinic import Doctor

            doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Врач с ID {specialist_id} не найден",
                )

            if specialist_id not in services_by_specialist:
                services_by_specialist[specialist_id] = []
            services_by_specialist[specialist_id].append(service_item)

        logger.debug(
            f"[create_queue_entries_batch] Группировка услуг: {len(services_by_specialist)} уникальных специалистов"
        )

        # Создаем записи в очереди для каждого специалиста
        created_entries = []
        reused_entries_count = 0

        for specialist_id, services_list in services_by_specialist.items():
            doctor = db.query(Doctor).filter(Doctor.id == specialist_id).first()
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Врач с ID {specialist_id} не найден",
                )

            queue_tag = None
            if services_list:
                first_service = db.query(Service).filter(Service.id == services_list[0].service_id).first()
                queue_tag = getattr(first_service, "queue_tag", None)

            daily_queue = queue_service.get_or_create_daily_queue(
                db,
                day=today,
                specialist_id=doctor.id,
                queue_tag=queue_tag,
                defaults={
                    "max_online_entries": doctor.max_online_per_day,
                    "cabinet_number": doctor.cabinet,
                },
            )

            # Проверяем дубликаты (для любых source)
            if daily_queue:
                existing_entry = (
                    db.query(OnlineQueueEntry)
                    .filter(
                        OnlineQueueEntry.queue_id == daily_queue.id,
                        OnlineQueueEntry.patient_id == request.patient_id,
                        OnlineQueueEntry.status.in_(
                            ["waiting", "called"]
                        ),  # Активные записи
                    )
                    .first()
                )

                if existing_entry:
                    logger.warning(
                        f"[create_queue_entries_batch] Пациент {request.patient_id} уже в очереди "
                        f"к специалисту {specialist_id} (queue_id={daily_queue.id}, entry_id={existing_entry.id})"
                    )
                    # Пропускаем создание дубликата, но добавляем существующую запись в ответ
                    created_entries.append(
                        BatchQueueEntryResponse(
                            specialist_id=specialist_id,
                            queue_id=daily_queue.id,
                            number=existing_entry.number,
                            queue_time=(
                                existing_entry.queue_time.isoformat()
                                if existing_entry.queue_time
                                else current_time.isoformat()
                            ),
                        )
                    )
                    reused_entries_count += 1
                    continue

            # [OK] Используем SSOT queue_service для создания записи
            # Это гарантирует правильную логику:
            # - Автоматическое создание DailyQueue если не существует
            # - Корректное присвоение номера в очереди
            # - Проверка дубликатов
            # - Установка queue_time

            try:
                # Получаем имя и телефон пациента
                patient_name = (
                    patient.short_name()
                    if hasattr(patient, 'short_name')
                    else f"{patient.last_name} {patient.first_name}"
                )
                patient_phone = patient.phone or None

                # Создаем запись через SSOT
                queue_entry = queue_service.create_queue_entry(
                    db,
                    daily_queue=daily_queue,
                    patient_id=request.patient_id,
                    patient_name=patient_name,
                    phone=patient_phone,
                    source=request.source,  # ⭐ Сохраняем оригинальный source!
                    queue_time=current_time,  # ⭐ Текущее время для справедливого присвоения номера
                    auto_number=True,
                    commit=False,
                )

                logger.info(
                    f"[create_queue_entries_batch] [OK] Создана запись: specialist_id={specialist_id}, "
                    f"queue_id={queue_entry.queue_id}, number={queue_entry.number}, source={request.source}"
                )

                # Получаем queue_id из созданной записи
                queue = (  # noqa: F841  # manual-review: variable intentionally kept for debugging/future use
                    db.query(DailyQueue)
                    .filter(DailyQueue.id == queue_entry.queue_id)
                    .first()
                )

                created_entries.append(
                    BatchQueueEntryResponse(
                        specialist_id=specialist_id,
                        queue_id=queue_entry.queue_id,
                        number=queue_entry.number,
                        queue_time=(
                            queue_entry.queue_time.isoformat()
                            if queue_entry.queue_time
                            else current_time.isoformat()
                        ),
                    )
                )

            except ValueError as ve:
                # queue_service может выбросить ValueError если что-то не так
                logger.error(f"[create_queue_entries_batch] Ошибка валидации: {ve}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Ошибка создания записи для специалиста {specialist_id}: {str(ve)}",
                )

        db.commit()

        entries_count = len(created_entries)
        created_count = max(entries_count - reused_entries_count, 0)
        if reused_entries_count and created_count:
            message = (
                f"Создано {created_count} записей в очереди; "
                f"{reused_entries_count} запись уже существовала"
            )
        elif reused_entries_count:
            message = "Запись уже существовала в очереди"
        else:
            message = (
                f"Создано {entries_count} "
                f"{'записей' if entries_count != 1 else 'запись'} в очереди"
            )

        return BatchQueueEntriesResponse(
            success=True,
            entries=created_entries,
            message=message,
        )

    except HTTPException:
        # Пробрасываем HTTPException без изменений
        raise
    except Exception as e:
        # Логируем и оборачиваем непредвиденные ошибки
        logger.error(
            f"[create_queue_entries_batch] Непредвиденная ошибка: {type(e).__name__}: {e}"
        )

        logger.exception("Registrar operation failed")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )


# ===================== КОНВЕРТАЦИЯ DOCTOR_ID → USER_ID =====================


@router.get("/registrar-integration/doctors/{doctor_id}/user-id", response_model=dict[str, Any])
def get_doctor_user_id(
    doctor_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    DEPRECATED: legacy compatibility bridge for doctor -> user lookup.

    Operational queue flows canonically use Doctor.id. This endpoint remains
    only as a transitional bridge and should not be treated as the source of truth.

    Args:
        doctor_id: ID врача из таблицы doctors

    Returns:
        user_id: ID пользователя из таблицы users

    Raises:
        HTTPException 404: Если врач не найден или у врача нет user_id
    """
    try:
        from app.models.clinic import Doctor

        doctor = db.query(Doctor).filter(Doctor.id == doctor_id).first()

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач с ID {doctor_id} не найден",
            )

        if not doctor.user_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"У врача с ID {doctor_id} не установлен user_id",
            )

        return {
            "doctor_id": doctor_id,
            "canonical_specialist_id": doctor.id,
            "user_id": doctor.user_id,
            "doctor_name": doctor.user.full_name if doctor.user else None,
            "deprecated": True,
            "note": "Use doctor_id as the canonical specialist identifier in queue flows.",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения user_id для doctor_id={doctor_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Внутренняя ошибка сервера. Подробности в журнале.",
        )

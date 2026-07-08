"""Split from qr_queue.py.
"""
from __future__ import annotations

from app.api.v1.endpoints.qr_queue._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.qr_queue._helpers import (
    router,
    _ensure_doctor_can_mutate_queue_entry,
    _queue_phone_matches,
)


@router.put("/online-entry/{entry_id}/update", response_model=dict[str, Any])
def update_online_entry(
    entry_id: int,
    request: UpdateOnlineEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """
    Обновляет данные пациента в онлайн записи
    """
    try:
        from app.models.online_queue import OnlineQueueEntry
        from app.models.patient import Patient

        # Находим запись
        entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )

        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
            )

        # Обновляем данные в OnlineQueueEntry
        _ensure_doctor_can_mutate_queue_entry(
            db,
            entry=entry,
            current_user=current_user,
        )

        if request.patient_name is not None:
            entry.patient_name = request.patient_name

        if request.phone is not None:
            entry.phone = request.phone

        if request.birth_year is not None:
            entry.birth_year = request.birth_year

        if request.address is not None:
            entry.address = request.address

        # Если есть patient_id, обновляем также данные в Patient
        if entry.patient_id:
            patient = db.query(Patient).filter(Patient.id == entry.patient_id).first()
            if patient:
                if request.patient_name:
                    # Разбираем ФИО
                    name_parts = request.patient_name.split()
                    if len(name_parts) >= 1:
                        patient.last_name = name_parts[0]
                    if len(name_parts) >= 2:
                        patient.first_name = name_parts[1]
                    if len(name_parts) >= 3:
                        patient.middle_name = name_parts[2]

                if request.phone:
                    patient.phone = request.phone

                if request.birth_year:
                    from datetime import date

                    patient.birth_date = date(request.birth_year, 1, 1)

                if request.address:
                    patient.address = request.address

        db.commit()
        db.refresh(entry)

        return {
            "success": True,
            "message": "Данные пациента обновлены",
            "entry": {
                "id": entry.id,
                "patient_name": entry.patient_name,
                "phone": entry.phone,
            },
        }

    except HTTPException:
        raise
    except Exception as e:

        logger.error(
            "[update_online_entry] Ошибка: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ПОЛНОЕ ОБНОВЛЕНИЕ ОНЛАЙН ЗАПИСИ (ДЛЯ МАСТЕРА) =====================


class FullUpdateOnlineEntryRequest(BaseModel):
    """Запрос на полное обновление онлайн записи через мастер регистрации"""

    patient_data: dict  # {patient_name, phone, birth_year, address}
    visit_type: str  # paid/repeat/benefit
    discount_mode: str  # none/repeat/benefit
    services: list[dict]  # [{service_id, quantity}]
    all_free: bool = False
    aggregated_ids: list[int] | None = None  # ⭐ FIX: IDs of all merged entries for dedup check


def _full_update_find_and_validate_entry(
    db: Session,
    entry_id: int,
    current_user: User,
):
    """Find queue entry by ID and validate doctor access."""
    from app.models.online_queue import OnlineQueueEntry

    entry = (
        db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    )

    if not entry:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена"
        )

    logger.info(
        "[full_update_online_entry] Запись найдена: %s, phone=%s",
        entry.patient_name,
        entry.phone,
    )

    _ensure_doctor_can_mutate_queue_entry(
        db,
        entry=entry,
        current_user=current_user,
    )

    original_entry_discount_mode = entry.discount_mode
    return entry, original_entry_discount_mode


def _full_update_patient_data(entry, patient_data: dict):
    """Update patient name, phone, birth_year, address on the queue entry."""
    if patient_data.get("patient_name"):
        entry.patient_name = patient_data["patient_name"]
        logger.info(
            "[full_update_online_entry] Обновлено ФИО: %s",
            entry.patient_name,
        )

    if patient_data.get("phone"):
        entry.phone = patient_data["phone"]
        logger.info(
            "[full_update_online_entry] Обновлен телефон: %s",
            entry.phone,
        )

    if patient_data.get("birth_year") is not None:
        entry.birth_year = patient_data["birth_year"]
        logger.info(
            "[full_update_online_entry] Обновлен год рождения: %s",
            entry.birth_year,
        )

    if patient_data.get("address"):
        entry.address = patient_data["address"]
        logger.info(
            "[full_update_online_entry] Обновлен адрес: %s",
            entry.address,
        )


def _full_update_visit_type(entry, request):
    """Update visit type and discount mode on the queue entry."""
    entry.visit_type = request.visit_type
    entry.discount_mode = "all_free" if request.all_free else request.discount_mode
    logger.info(
        "[full_update_online_entry] Тип визита: %s, режим скидки: %s, all_free: %s",
        entry.visit_type,
        entry.discount_mode,
        request.all_free,
    )


def _full_update_sync_patient_and_entries(
    db: Session,
    entry,
    patient_data: dict,
):
    """Section 5.1: Update Patient record + sync other queue_entries in same visit/session.

    - Updates Patient.name/phone/birth_date/address from patient_data.
    - Finds other OnlineQueueEntry records in the same visit or session and
      syncs patient fields (preserving their queue_time and number).
    - For other_entries with a visit_id, refreshes services from VisitService.
    """
    import json
    from datetime import date

    from app.models.online_queue import OnlineQueueEntry
    from app.models.patient import Patient

    # 5. Если есть patient_id, обновляем также запись Patient
    if entry.patient_id:
        patient = db.query(Patient).filter(Patient.id == entry.patient_id).first()
        if patient:
            logger.info(
                "[full_update_online_entry] Обновление связанного пациента ID=%d",
                patient.id,
            )

            if patient_data.get('patient_name'):
                # Разбираем ФИО на компоненты
                name_parts = patient_data['patient_name'].split()
                if len(name_parts) >= 1:
                    patient.last_name = name_parts[0]
                if len(name_parts) >= 2:
                    patient.first_name = name_parts[1]
                if len(name_parts) >= 3:
                    patient.middle_name = name_parts[2]

            if patient_data.get('phone'):
                patient.phone = patient_data['phone']

            if patient_data.get('birth_year'):
                patient.birth_date = date(patient_data['birth_year'], 1, 1)

            if patient_data.get('address'):
                patient.address = patient_data['address']

            logger.info(
                "[full_update_online_entry] Пациент обновлен: %s %s",
                patient.last_name,
                patient.first_name,
            )

            # Keep duplicate service entries in the same visit/session aligned.
            # Patient-wide sync can rewrite unrelated historical/future entries.
            other_entry_filters = [
                OnlineQueueEntry.patient_id == entry.patient_id,
                OnlineQueueEntry.id
                != entry.id,  # Исключаем текущую запись (уже обновлена)
            ]
            if entry.visit_id:
                other_entry_filters.append(
                    OnlineQueueEntry.visit_id == entry.visit_id
                )
            elif entry.session_id:
                other_entry_filters.extend(
                    [
                        OnlineQueueEntry.visit_id.is_(None),
                        OnlineQueueEntry.session_id == entry.session_id,
                    ]
                )
            else:
                other_entry_filters.extend(
                    [
                        OnlineQueueEntry.visit_id.is_(None),
                        OnlineQueueEntry.queue_id == entry.queue_id,
                    ]
                )

            other_entries = (
                db.query(OnlineQueueEntry)
                .filter(*other_entry_filters)
                .all()
            )

            if other_entries:
                logger.info(
                    "[full_update_online_entry] Синхронизация данных в %d других queue_entries для пациента %d",
                    len(other_entries),
                    entry.patient_id,
                )
                for other_entry in other_entries:
                    # ⭐ Queue Integrity Patch: Защита от перезаписи старого времени и номера
                    # Сохраняем оригинальные значения перед обновлением
                    original_queue_time = other_entry.queue_time
                    original_number = other_entry.number

                    # Обновляем только те поля, которые были переданы
                    if patient_data.get('patient_name'):
                        other_entry.patient_name = patient_data['patient_name']
                    if patient_data.get('phone'):
                        other_entry.phone = patient_data['phone']
                    if patient_data.get('birth_year') is not None:
                        other_entry.birth_year = patient_data['birth_year']
                    if patient_data.get('address'):
                        other_entry.address = patient_data['address']

                    # ⭐ ВАЖНО: Восстанавливаем queue_time и number (не перезаписываем!)
                    if original_queue_time:
                        other_entry.queue_time = original_queue_time
                    if original_number:
                        other_entry.number = original_number
                    logger.info(
                        "[full_update_online_entry] ✅ Защита: сохранены queue_time=%s, number=%s для entry_id=%d",
                        original_queue_time,
                        original_number,
                        other_entry.id,
                    )

                    # ⭐ ИСПРАВЛЕНО: НЕ копируем услуги между queue_entries
                    # Каждая queue_entry должна получать услуги только из своего Visit
                    # Синхронизация услуг между записями удалена во избежание дублирования

                    # Если у other_entry есть visit_id, синхронизируем услуги из Visit
                    if other_entry.visit_id:
                        from app.models.visit import VisitService

                        visit_services = (
                            db.query(VisitService)
                            .filter(VisitService.visit_id == other_entry.visit_id)
                            .all()
                        )

                        if visit_services:
                            # Формируем JSON со услугами из Visit
                            visit_services_list = []
                            visit_total = 0

                            for vs in visit_services:
                                vs_price = float(vs.price) if vs.price else 0
                                vs_qty = vs.qty or 1
                                visit_total += vs_price * vs_qty

                                service_obj = {
                                    'service_id': vs.service_id,
                                    'name': vs.name,
                                    'code': vs.code,
                                    'quantity': vs_qty,
                                    'price': int(vs_price),
                                    'queue_time': (
                                        other_entry.queue_time.isoformat()
                                        if other_entry.queue_time
                                        else None
                                    ),
                                    'cancelled': False,
                                    'cancel_reason': None,
                                    'cancelled_by': None,
                                    'was_paid_before_cancel': False,
                                }
                                visit_services_list.append(service_obj)

                            # Обновляем услуги из Visit (не копируем из других queue_entries!)
                            other_entry.services = json.dumps(
                                visit_services_list, ensure_ascii=False
                            )
                            other_entry.total_amount = int(visit_total)
                            logger.info(
                                "[full_update_online_entry] ✅ Синхронизировано %d услуг из Visit %d для entry %d",
                                len(visit_services_list),
                                other_entry.visit_id,
                                other_entry.id,
                            )

                logger.info(
                    "[full_update_online_entry] ✅ Синхронизировано %d записей",
                    len(other_entries),
                )




def _full_update_finalize_and_respond(
    db: Session,
    entry,
    request,
    visit,
    total_amount: int,
    services_list: list,
    service_codes_list: list,
    original_entry_discount_mode: str,
    current_user,
    entry_id: int,
    patient_data: dict,
):
    """Section 5: Update patient record, handle all_free approval, build response."""
    try:
        # Section 5.1: Update Patient record + sync other queue_entries
        _full_update_sync_patient_and_entries(
            db=db,
            entry=entry,
            patient_data=patient_data,
        )

        # ✅ ИСПРАВЛЕНО: Коммитим все изменения одной транзакцией
        try:
            db.commit()
            db.refresh(entry)

            # ✅ Проверяем, что Visit правильно связан с OnlineQueueEntry (если all_free)
            if request.all_free and visit:
                db.refresh(visit)
                if entry.visit_id != visit.id:
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Предупреждение: entry.visit_id (%s) != visit.id (%d), исправляем...",
                        entry.visit_id,
                        visit.id,
                    )
                    entry.visit_id = visit.id
                    db.commit()
                    db.refresh(entry)

            # ✅ Проверяем количество VisitService для отладки (если all_free)
            if request.all_free and visit:
                from app.models.visit import VisitService

                visit_services_count = (
                    db.query(VisitService)
                    .filter(VisitService.visit_id == visit.id)
                    .count()
                )
                logger.info(
                    "[full_update_online_entry] ✅ Финальная проверка: Visit %d имеет %d услуг (ожидалось %d)",
                    visit.id,
                    visit_services_count,
                    len(request.services),
                )
                if visit_services_count != len(request.services):
                    logger.warning(
                        "[full_update_online_entry] ⚠️ Предупреждение: Количество услуг не совпадает! Возможно дубликаты.",
                    )

            logger.info("[full_update_online_entry] Запись успешно обновлена")

            return {
                "success": True,
                "message": "Запись успешно обновлена",
                "entry": {
                    "id": entry.id,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "birth_year": entry.birth_year,
                    "address": entry.address,
                    "services": services_list,
                    "service_codes": service_codes_list,
                    "total_amount": total_amount,
                    "discount_mode": entry.discount_mode,
                    "visit_type": entry.visit_type,
                    "all_free": request.all_free,
                    "visit_id": entry.visit_id if request.all_free else None,
                },
            }
        except Exception as commit_error:
            db.rollback()

            logger.error(
                "[full_update_online_entry] ❌ Ошибка при коммите: %s: %s",
                type(commit_error).__name__,
                str(commit_error),
                exc_info=True,
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Ошибка сохранения изменений: {str(commit_error)}",
            )

    except HTTPException:
        raise
    except Exception as e:

        logger.error(
            "[full_update_online_entry] Ошибка: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )



def _full_update_resolve_visit_metadata(
    db: Session,
    entry,
    request,
):
    """Section 4.6.1: Resolve visit_date, doctor_id, department, and original_total_amount."""
    from datetime import date
    from decimal import Decimal

    from app.models.online_queue import DailyQueue
    from app.models.service import Service

    # Получаем данные из связанной очереди
    queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
    visit_date = queue.day if queue else date.today()
    doctor_id = queue.specialist_id if queue else None

    # ✅ ИСПРАВЛЕНО: Определяем department из queue_tag или по услугам
    department = None
    if queue and queue.queue_tag:
        # Маппинг queue_tag -> department
        queue_tag_to_dept = {
            'cardiology': 'cardiology',
            'cardio': 'cardiology',
            'dermatology': 'dermatology',
            'derma': 'dermatology',
            'stomatology': 'stomatology',
            'dentist': 'stomatology',
            'lab': 'laboratory',
            'laboratory': 'laboratory',
            'ecg': 'cardiology',
            'echokg': 'cardiology',
        }
        department = queue_tag_to_dept.get(queue.queue_tag.lower())

    # Если не определили по queue_tag, определяем по услугам
    if not department and request.services:
        for service_item in request.services:
            service = (
                db.query(Service)
                .filter(Service.id == service_item['service_id'])
                .first()
            )
            if service:
                # Resolve department through the queue-group SSOT.
                service_code = service.service_code or get_service_code(
                    service.id, db
                )
                queue_group = get_queue_group_for_service(service_code)
                service_group_to_dept = {
                    'cardiology': 'cardiology',
                    'ecg': 'cardiology',
                    'dermatology': 'dermatology',
                    'dental': 'stomatology',
                    'laboratory': 'laboratory',
                }
                department = service_group_to_dept.get(queue_group)
                if department:
                    break

    # Если department все еще не определен, используем значение по умолчанию
    if not department:
        department = 'general'

    # Вычисляем оригинальную сумму (без скидки all_free)
    original_total_amount = Decimal('0')
    for service_item in request.services:
        service = (
            db.query(Service)
            .filter(Service.id == service_item['service_id'])
            .first()
        )
        if service:
            original_total_amount += (
                service.price or Decimal('0')
            ) * service_item.get('quantity', 1)

    return (visit_date, doctor_id, department, original_total_amount)


def _full_update_ensure_patient_for_visit(
    db: Session,
    entry,
    patient_data: dict,
):
    """Section 4.6.2: Create temp Patient if entry has no patient_id. Returns patient_id_for_visit."""
    from datetime import date

    from app.models.patient import Patient

    # ✅ ИСПРАВЛЕНО: Для QR-пациентов без patient_id нужно создать Patient или пропустить создание Visit
    # Но Visit требует patient_id (nullable=False), поэтому создаем временного пациента если нужно
    patient_id_for_visit = entry.patient_id
    if not patient_id_for_visit:
        # ✅ ИСПРАВЛЕНО: Создаем временного пациента используя единую функцию нормализации
        logger.info(
            "[full_update_online_entry] Создание временного пациента для QR-записи",
        )
        from app.crud.patient import normalize_patient_name

        patient_name = patient_data.get('patient_name', 'Неизвестный пациент')
        name_parts = normalize_patient_name(full_name=patient_name)

        # Гарантируем, что поля не пустые
        last_name = name_parts["last_name"] or 'Неизвестный'
        first_name = name_parts["first_name"] or 'Пациент'

        temp_patient = Patient(
            last_name=last_name,
            first_name=first_name,
            middle_name=name_parts.get("middle_name"),
            phone=patient_data.get('phone', ''),
            birth_date=(
                date(patient_data.get('birth_year', 1990), 1, 1)
                if patient_data.get('birth_year')
                else None
            ),
            address=patient_data.get('address', ''),
        )
        db.add(temp_patient)
        db.flush()
        patient_id_for_visit = temp_patient.id
        # ✅ Связываем OnlineQueueEntry с созданным пациентом
        entry.patient_id = patient_id_for_visit
        logger.info(
            "[full_update_online_entry] Создан временный пациент ID=%d и связан с OnlineQueueEntry",
            patient_id_for_visit,
        )

    return patient_id_for_visit


def _full_update_find_existing_visit(
    db: Session,
    entry,
    patient_id_for_visit: int,
    visit_date,
):
    """Section 4.6.3: 3-priority lookup for existing Visit.

    Priority 1: entry.visit_id. Priority 2: patient_id + visit_date.
    Priority 3: patient_id + visit_date + all_free. Returns Visit or None."""
    from app.models.visit import Visit

    # ✅ ИСПРАВЛЕНО: Улучшенный поиск существующего Visit для предотвращения дублирования
    visit = None

    # Приоритет 1: Ищем по entry.visit_id (если уже связан)
    if entry.visit_id:
        visit = db.query(Visit).filter(Visit.id == entry.visit_id).first()
        if visit:
            if visit.patient_id != patient_id_for_visit:
                logger.warning(
                    "[full_update_online_entry] entry visit owner mismatch entry_id=%d visit_id=%d",
                    entry.id,
                    visit.id,
                )
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Queue entry visit does not belong to the queue patient",
                )
            logger.info(
                "[full_update_online_entry] Найден Visit по entry.visit_id: %d",
                visit.id,
            )

    # Приоритет 2: Если не найден, ищем по patient_id + visit_date (без фильтра по discount_mode)
    # Это важно, так как при первом редактировании может быть создан Visit с другим discount_mode
    if not visit and patient_id_for_visit:
        visit = (
            db.query(Visit)
            .filter(
            Visit.id == entry.visit_id,
            Visit.patient_id == patient_id_for_visit,
                Visit.visit_date == visit_date,
            )
            .order_by(Visit.created_at.desc())
            .first()
        )  # Берем самый последний
        if visit:
            logger.info(
                "[full_update_online_entry] Найден Visit по patient_id + visit_date: %d, discount_mode=%s",
                visit.id,
                visit.discount_mode,
            )

    # Приоритет 3: Если все еще не найден, ищем по patient_id + visit_date + discount_mode="all_free"
    if not visit and patient_id_for_visit:
        visit = (
            db.query(Visit)
            .filter(
            Visit.id == entry.visit_id,
            Visit.patient_id == patient_id_for_visit,
            Visit.visit_date == visit_date,
                Visit.discount_mode == "all_free",
            )
            .first()
        )
        if visit:
            logger.info(
                "[full_update_online_entry] Найден Visit по patient_id + visit_date + all_free: %d",
                visit.id,
            )

    return visit


def _full_update_add_services_to_visit(
    db: Session,
    visit,
    request,
    has_paid_invoice: bool,
):
    """Section 4.6.4: Add VisitService records to the Visit.

    For each service in request.services, create or update VisitService.
    All services get price=0 (all_free). Returns list of added/updated service names."""
    from decimal import Decimal

    from app.models.service import Service
    from app.models.visit import VisitService

    # ✅ ИСПРАВЛЕНО: Добавляем услуги к Visit (после удаления старых ИЛИ к существующим)
    added_services = []
    for service_item in request.services:
        service = (
            db.query(Service)
            .filter(Service.id == service_item['service_id'])
            .first()
        )
        if service:
            # ✅ Проверяем, нет ли уже такой услуги
            existing_service = (
                db.query(VisitService)
                .filter(
                VisitService.visit_id == visit.id,
                    VisitService.service_id == service.id,
                )
                .first()
            )

            if not existing_service:
                # ⭐ ИСПРАВЛЕНИЕ #2: Добавляем новую услугу (работает и для оплаченных, и для неоплаченных)
                # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                service_code = service.service_code or get_service_code(
                    service.id, db
                )
                visit_service = VisitService(
                    visit_id=visit.id,
                    service_id=service.id,
                    code=service_code,
                    name=service.name,
                    qty=service_item.get('quantity', 1),
                    price=Decimal('0'),  # All Free - всё бесплатно
                    currency="UZS",
                )
                db.add(visit_service)
                added_services.append(service.name)
                if has_paid_invoice:
                    logger.info(
                        "[full_update_online_entry] ✅ Добавлена НОВАЯ услуга к оплаченному визиту: %s",
                        service.name,
                    )
            else:
                # Обновляем количество если услуга уже есть
                existing_service.qty = service_item.get('quantity', 1)
                added_services.append(f"{service.name} (обновлено)")

    db.flush()  # Коммитим добавление услуг
    logger.info(
        "[full_update_online_entry] Visit ID=%d обновлен с услугами для all_free: %s",
        visit.id,
        added_services,
    )

    return added_services


def _full_update_handle_all_free_visit(
    db: Session,
    entry,
    request,
    original_entry_discount_mode: str,
    patient_data,
    services_list,
    service_codes_list,
    total_amount,
):
    """Section 4.6: If request.all_free, create or update Visit + VisitService records.

    Returns the Visit (or None if all_free is False).
    """
    from datetime import date
    from decimal import Decimal

    from app.models.visit import Visit, VisitService

    visit = None
    if not request.all_free:
        return visit

    logger.info(
        "[full_update_online_entry] all_free=True, создаем/обновляем Visit для одобрения",
    )

    # Section 4.6.1: Resolve visit metadata
    visit_date, doctor_id, department, original_total_amount = (
        _full_update_resolve_visit_metadata(db=db, entry=entry, request=request)
    )

    # Section 4.6.2: Ensure patient exists for Visit
    patient_id_for_visit = _full_update_ensure_patient_for_visit(
        db=db, entry=entry, patient_data=patient_data,
    )

    # Section 4.6.3: Find existing Visit (3-priority lookup)
    visit = _full_update_find_existing_visit(
        db=db,
        entry=entry,
        patient_id_for_visit=patient_id_for_visit,
        visit_date=visit_date,
    )

    has_paid_invoice = False
    if visit:
        # ✅ ИСПРАВЛЕНО: Обновляем существующий Visit (не создаем новый)
        logger.info(
            "[full_update_online_entry] Обновление существующего Visit ID=%d",
            visit.id,
        )
        # ⭐ ИСПРАВЛЕНИЕ #2: Проверяем есть ли оплаченный инвойс перед удалением услуг
        from app.models.payment_invoice import (
            PaymentInvoice,
            PaymentInvoiceVisit,
        )

        has_paid_invoice = (
            db.query(PaymentInvoiceVisit)
            .join(PaymentInvoice)
            .filter(
            PaymentInvoiceVisit.visit_id == visit.id,
                PaymentInvoice.status == 'paid',
            )
            .first()
        )

        if has_paid_invoice:
            # ⚠️ Визит УЖЕ оплачен - НЕ меняем платежный режим/статус и НЕ удаляем существующие услуги.
            # Только добавляем новые услуги к уже существующим.
            entry.discount_mode = original_entry_discount_mode
            logger.warning(
                "[full_update_online_entry] ⚠️ Visit %d имеет оплаченный инвойс - НЕ меняем payment state и НЕ удаляем услуги, только добавляем новые",
                visit.id,
            )
            deleted_count = 0
        else:
            visit.approval_status = (
                "pending"  # Сбрасываем статус на pending при обновлении
            )
            visit.discount_mode = "all_free"  # Убеждаемся, что режим правильный
            visit.department = department  # Обновляем department
            visit.doctor_id = doctor_id  # Обновляем doctor_id

            # ✅ Визит не оплачен - безопасно удалять и пересоздавать услуги
            deleted_count = (
                db.query(VisitService)
                .filter(VisitService.visit_id == visit.id)
                .delete()
            )
            db.flush()  # Коммитим удаление перед добавлением новых
            logger.info(
                "[full_update_online_entry] Удалено старых услуг: %d",
                deleted_count,
            )

        # ✅ Связываем OnlineQueueEntry с Visit (если еще не связан)
        if not entry.visit_id or entry.visit_id != visit.id:
            entry.visit_id = visit.id
            logger.info(
                "[full_update_online_entry] Связан OnlineQueueEntry %d с Visit %d",
                entry.id,
                visit.id,
            )

        # ✅ ИСПРАВЛЕНО: Синхронизируем discount_mode в OnlineQueueEntry с Visit
        if not has_paid_invoice and entry.discount_mode != "all_free":
            entry.discount_mode = "all_free"
            logger.info(
                "[full_update_online_entry] Синхронизирован discount_mode в OnlineQueueEntry %d с Visit %d",
                entry.id,
                visit.id,
            )
    else:
        # ✅ Создаем новый Visit только если действительно не найден существующий
        logger.info(
            "[full_update_online_entry] Создание нового Visit для all_free (существующий не найден)",
        )
        visit = Visit(
            patient_id=patient_id_for_visit,
            doctor_id=doctor_id,
            visit_date=visit_date,
            visit_time=None,  # Время не сохраняется в OnlineQueueEntry
            department=department,
            discount_mode="all_free",
            approval_status="pending",
            notes=f"All Free заявка из онлайн записи #{entry.id}",
            source="online",  # ✅ SSOT: QR-запись
        )
        db.add(visit)
        db.flush()  # Получаем ID визита

        # Связываем OnlineQueueEntry с Visit
        entry.visit_id = visit.id

        # ✅ ИСПРАВЛЕНО: Синхронизируем discount_mode в OnlineQueueEntry с Visit
        entry.discount_mode = "all_free"

        logger.info(
            "[full_update_online_entry] Visit создан с ID=%d, department=%s, discount_mode синхронизирован",
            visit.id,
            department,
        )


    # Section 4.6.4: Add services to Visit
    _full_update_add_services_to_visit(
        db=db,
        visit=visit,
        request=request,
        has_paid_invoice=has_paid_invoice,
    )

    return visit




def _full_update_collect_existing_services(
    db: Session,
    entry,
    request,
):
    """Section 4.1+4.2: Compute aggregated_ids and collect existing service_ids + queue_times.

    Returns (existing_service_ids, existing_service_queue_times, final_aggregated_ids).
    """
    import json
    from datetime import date

    from app.models.online_queue import DailyQueue, OnlineQueueEntry

    existing_service_ids = set()
    # ⭐ FIX PHASE 2: Сохраняем оригинальные queue_times для существующих услуг
    existing_service_queue_times = {}

    # ⭐ FIX 3: Backend САМ вычисляет aggregated_ids по patient_id + дате или phone + дате
    # Frontend aggregated_ids используем только как fallback
    computed_aggregated_ids = []
    today = date.today()

    queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
    queue_day = queue.day if queue else today

    if entry.visit_id:
        # ⭐ FIX 4: Если есть visit_id, ищем строго по нему (это одна сессия обслуживания)
        visit_entry_filters = [
            OnlineQueueEntry.visit_id == entry.visit_id,
            OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]),
        ]
        if entry.patient_id is not None:
            visit_entry_filters.append(
                OnlineQueueEntry.patient_id == entry.patient_id
            )
        else:
            visit_entry_filters.append(OnlineQueueEntry.id == entry.id)
            logger.warning(
                "[full_update_online_entry] visit-linked entry %d has no patient_id; using current entry only for aggregation",
                entry.id,
            )
        visit_entries = (
            db.query(OnlineQueueEntry)
            .filter(*visit_entry_filters)
            .all()
        )
        computed_aggregated_ids = [e.id for e in visit_entries]
        logger.info(
            "[full_update_online_entry] computed %d aggregated ids by visit_id with same-patient guard",
            len(computed_aggregated_ids),
        )
    else:
        # If there is no visit yet, aggregate only the current service
        # session. Same-day patient/phone scans can treat unrelated queue
        # entries as already having the requested services.
        session_filters = [
            DailyQueue.day == queue_day,
            OnlineQueueEntry.visit_id.is_(None),
            OnlineQueueEntry.status.in_(["waiting", "called", "in_service"]),
        ]
        session_label = None

        if entry.patient_id:
            session_filters.append(OnlineQueueEntry.patient_id == entry.patient_id)
            session_label = "patient_id"
        elif entry.phone:
            session_label = "phone"

        if session_label:
            if entry.session_id:
                session_filters.append(
                    OnlineQueueEntry.session_id == entry.session_id
                )
                boundary_label = "session_id"
            else:
                session_filters.append(OnlineQueueEntry.queue_id == entry.queue_id)
                boundary_label = "queue_id"

            session_entries = (
                db.query(OnlineQueueEntry)
                .join(DailyQueue, OnlineQueueEntry.queue_id == DailyQueue.id)
                .filter(*session_filters)
                .all()
            )
            if session_label == "phone":
                session_entries = [
                    candidate
                    for candidate in session_entries
                    if _queue_phone_matches(candidate.phone, entry.phone)
                ]
            computed_aggregated_ids = list(
                set([e.id for e in session_entries] + [entry.id])
            )
            logger.info(
                "[full_update_online_entry] computed %d aggregated ids by %s bounded by %s (no visit)",
                len(computed_aggregated_ids),
                session_label,
                boundary_label,
            )

    def _same_fallback_aggregation_scope(
        candidate: OnlineQueueEntry,
    ) -> bool:
        if candidate.id == entry.id:
            return True

        if entry.visit_id:
            if candidate.visit_id != entry.visit_id:
                return False
            if entry.patient_id is None:
                return False
            return candidate.patient_id == entry.patient_id

        if candidate.visit_id is not None:
            return False

        if entry.patient_id is not None:
            return candidate.patient_id == entry.patient_id

        if entry.phone:
            same_boundary = (
                candidate.session_id == entry.session_id
                if entry.session_id
                else candidate.queue_id == entry.queue_id
            )
            return same_boundary and _queue_phone_matches(candidate.phone, entry.phone)

        return False

    # Используем computed_aggregated_ids; frontend aggregated_ids are only
    # an advisory fallback and must not cross queue-entry identity scopes.
    if computed_aggregated_ids:
        final_aggregated_ids = computed_aggregated_ids
    elif request.aggregated_ids:
        requested_aggregated_ids = [
            int(aggregated_id)
            for aggregated_id in request.aggregated_ids
            if aggregated_id is not None
        ]
        fallback_entries = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id.in_(requested_aggregated_ids))
            .all()
            if requested_aggregated_ids
            else []
        )
        safe_fallback_ids = [
            candidate.id
            for candidate in fallback_entries
            if _same_fallback_aggregation_scope(candidate)
        ]
        if entry.id not in safe_fallback_ids:
            safe_fallback_ids.append(entry.id)

        ignored_fallback_ids = sorted(
            set(requested_aggregated_ids) - set(safe_fallback_ids)
        )
        if ignored_fallback_ids:
            logger.warning(
                "[full_update_online_entry] ignored frontend aggregated_ids outside current entry scope: %s",
                ignored_fallback_ids,
            )

        final_aggregated_ids = safe_fallback_ids
        logger.warning(
            "[full_update_online_entry] ⚠️ Используем aggregated_ids из frontend (fallback): %s",
            final_aggregated_ids
        )
    else:
        final_aggregated_ids = []

    # ⭐ DEBUG: Логируем начальное состояние
    logger.info(
        "[full_update_online_entry] ⭐ DEBUG: entry.patient_id=%s, final_aggregated_ids=%s, entry.services=%s",
        entry.patient_id,
        final_aggregated_ids,
        entry.services[:200] if entry.services else None,
    )

    # ⭐ FIX: Используем final_aggregated_ids для получения всех записей пациента
    if final_aggregated_ids and len(final_aggregated_ids) > 0:
        logger.info(
            "[full_update_online_entry] ⭐ FIX: Используем aggregated_ids для поиска существующих услуг: %s",
            final_aggregated_ids,
        )
        all_entries = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id.in_(final_aggregated_ids))
            .all()
        )

        for agg_entry in all_entries:
            if agg_entry.services:
                try:
                    agg_services = json.loads(agg_entry.services)
                    # ⭐ FIX: Обрабатываем двойное кодирование JSON
                    if isinstance(agg_services, str):
                        agg_services = json.loads(agg_services)

                    if isinstance(agg_services, list):
                        for svc in agg_services:
                            svc_id = svc.get('service_id')
                            if svc_id:
                                existing_service_ids.add(svc_id)
                                # ⭐ FIX: Сохраняем оригинальное queue_time
                                if svc.get('queue_time') and svc_id not in existing_service_queue_times:
                                    existing_service_queue_times[svc_id] = svc.get('queue_time')
                except Exception as e:
                    logger.warning(
                        "[full_update_online_entry] Ошибка парсинга services для entry %d: %s",
                        agg_entry.id, e,
                    )

        logger.info(
            "[full_update_online_entry] ⭐ FIX: Найдено %d существующих услуг из aggregated_ids: %s",
            len(existing_service_ids),
            list(existing_service_ids),
        )

    # Используем queue из FIX 3 блока выше (queue_day уже вычислен)

    # ⭐ FIX: Если aggregated_ids не предоставлен или пустой, используем старую логику
    # Но ТОЛЬКО если мы ещё не нашли услуги через aggregated_ids
    if len(existing_service_ids) == 0:
        if entry.patient_id:
            # Limit fallback service detection to the same service session.
            all_patient_entry_filters = [
                OnlineQueueEntry.patient_id == entry.patient_id,
            ]
            if entry.visit_id:
                all_patient_entry_filters.append(
                    OnlineQueueEntry.visit_id == entry.visit_id
                )
            elif entry.session_id:
                all_patient_entry_filters.extend(
                    [
                        OnlineQueueEntry.visit_id.is_(None),
                        OnlineQueueEntry.session_id == entry.session_id,
                    ]
                )
            else:
                all_patient_entry_filters.extend(
                    [
                        OnlineQueueEntry.visit_id.is_(None),
                        OnlineQueueEntry.queue_id == entry.queue_id,
                    ]
                )

            all_patient_entries = (
                db.query(OnlineQueueEntry)
                .filter(*all_patient_entry_filters)
                .all()
            )

            logger.info(
                "[full_update_online_entry] ⭐ FIX: Найдено %d записей пациента в текущей сессии",
                len(all_patient_entries),
            )

            for patient_entry in all_patient_entries:
                if patient_entry.services:
                    try:
                        entry_services = json.loads(patient_entry.services)
                        for svc in entry_services:
                            svc_id = svc.get('service_id')
                            if svc_id:
                                existing_service_ids.add(svc_id)
                                # ⭐ FIX: Сохраняем оригинальное queue_time
                                if svc.get('queue_time') and svc_id not in existing_service_queue_times:
                                    existing_service_queue_times[svc_id] = svc.get('queue_time')
                    except Exception:
                        pass
        else:
            # Fallback: только текущая entry (как было раньше)
            logger.info(
                "[full_update_online_entry] ⭐ DEBUG: Fallback - patient_id is None or no queue, using entry.services only"
            )
            if entry.services:
                try:
                    # ⭐ FIX: Обрабатываем двойное кодирование JSON
                    existing_services = json.loads(entry.services)
                    # Если результат — строка, значит данные двойно закодированы
                    if isinstance(existing_services, str):
                        existing_services = json.loads(existing_services)
                        logger.warning(
                            "[full_update_online_entry] ⚠️ Обнаружено двойное кодирование JSON в entry.services"
                        )

                    if isinstance(existing_services, list):
                        logger.info(
                            "[full_update_online_entry] ⭐ DEBUG: Найдено %d услуг в entry.services: %s",
                            len(existing_services),
                            [s.get('service_id') for s in existing_services],
                        )
                        for svc in existing_services:
                            svc_id = svc.get('service_id')
                            if svc_id:
                                existing_service_ids.add(svc_id)
                                # ⭐ FIX: Сохраняем оригинальное queue_time
                                if svc.get('queue_time') and svc_id not in existing_service_queue_times:
                                    existing_service_queue_times[svc_id] = svc.get('queue_time')
                    else:
                        logger.warning(
                            "[full_update_online_entry] ⚠️ entry.services не является списком: %s",
                            type(existing_services).__name__
                        )
                except Exception as parse_err:
                    logger.error(
                        "[full_update_online_entry] ⭐ DEBUG: Ошибка парсинга entry.services: %s",
                        parse_err,
                    )

    logger.info(
        "[full_update_online_entry] Существующие услуги: %s, сохранённые queue_times: %s",
        existing_service_ids,
        list(existing_service_queue_times.keys()),
    )

    return existing_service_ids, existing_service_queue_times, final_aggregated_ids



def _full_update_resolve_target_queue_id(
    db: Session,
    entry,
    service,
):
    """Resolve the target DailyQueue ID for a service based on its queue_tag.

    If the service has a queue_tag, find or auto-create the matching DailyQueue.
    Otherwise, fall back to the entry's original queue_id.
    """
    from app.models.online_queue import DailyQueue

    default_queue_id = entry.queue_id
    if not service.queue_tag:
        return default_queue_id

    candidate_queue = (
        db.query(DailyQueue)
        .filter(
            DailyQueue.day == entry.queue.day,
            DailyQueue.queue_tag == service.queue_tag,
            DailyQueue.active == True,
        )
        .first()
    )
    if candidate_queue:
        logger.info(
            "[full_update_online_entry] 🔀 Услуга %s → очередь %s (ID=%d)",
            service.name, service.queue_tag, candidate_queue.id,
        )
        return candidate_queue.id

    # Auto-create DailyQueue if missing (NOT silent fallback)
    logger.warning(
        "[full_update_online_entry] ⚠️ DailyQueue for queue_tag=%s not found, creating...",
        service.queue_tag,
    )
    new_queue = queue_service.get_or_create_daily_queue(
        db,
        day=entry.queue.day,
        specialist_id=entry.queue.specialist_id,
        queue_tag=service.queue_tag,
    )
    logger.info(
        "[full_update_online_entry] ✅ Created DailyQueue for %s (ID=%d)",
        service.queue_tag, new_queue.id,
    )
    return new_queue.id


def _full_update_create_single_independent_entry(
    db: Session,
    entry,
    request,
    service,
    service_item_data: dict | None,
    current_queue_time,
):
    """Create a single IndependentQueueEntry for one service.

    Shared logic for both first_fill_qr (additional services) and editing
    (new services) branches. Computes target queue, next number, price with
    discounts, and creates the OnlineQueueEntry with services/service_codes JSON.
    """
    import json
    from datetime import datetime

    from sqlalchemy import text

    from app.models.online_queue import OnlineQueueEntry

    target_queue_id = _full_update_resolve_target_queue_id(db, entry, service)

    next_number = db.execute(
        text("SELECT COALESCE(MAX(number), 0) + 1 FROM queue_entries WHERE queue_id = :qid"),
        {"qid": target_queue_id},
    ).scalar()

    quantity = service_item_data.get("quantity", 1) if service_item_data else 1
    item_price = service.price * quantity

    if service.is_consultation and request.discount_mode in ["repeat", "benefit"]:
        item_price = 0
    if request.all_free:
        item_price = 0

    session_id = get_or_create_session_id(
        db, entry.patient_id, target_queue_id, entry.queue.day
    )

    service_code = (
        service.service_code
        or get_service_code(service.id, db)
        or "UNKNOWN"
    )

    new_entry = OnlineQueueEntry(
        queue_id=target_queue_id,
        number=next_number,
        queue_time=current_queue_time,
        patient_id=entry.patient_id,
        patient_name=entry.patient_name,
        phone=entry.phone,
        birth_year=entry.birth_year,
        address=entry.address,
        status="waiting",
        source=entry.source or "online",
        discount_mode=request.discount_mode or entry.discount_mode,
        visit_id=None,
        session_id=session_id,
        services=json.dumps(
            [
                {
                    "service_id": service.id,
                    "name": service.name,
                    "code": service_code,
                    "quantity": quantity,
                    "price": int(item_price),
                    "queue_time": current_queue_time.isoformat(),
                    "cancelled": False,
                }
            ],
            ensure_ascii=False,
        ),
        service_codes=json.dumps([service_code], ensure_ascii=False),
        total_amount=int(item_price),
    )
    db.add(new_entry)
    db.flush()

    logger.info(
        "[full_update_online_entry] ⭐ Created Independent Entry for %s (ID=%d), queue_id=%d, number=%d, time=%s",
        service.name,
        service.id,
        target_queue_id,
        next_number,
        current_queue_time,
    )
    return new_entry



def _full_update_create_independent_entries(
    db: Session,
    entry,
    request,
    existing_service_ids: set,
    existing_service_queue_times: dict,
    is_initial_registration: bool,
    is_first_fill_qr: bool,
    new_service_ids: list,
):
    """Section 4.4: Create Independent Queue Entries for new/additional services.

    Handles 3 branches:
    - is_initial_registration: just returns the effective queue_time.
    - is_first_fill_qr: finds the consultation service (gets QR time),
      creates IndependentQueueEntry for each additional service (gets current time),
      creates a Visit for the QR entry.
    - else (editing): creates IndependentQueueEntry for each new_service_id.

    Mutates existing_service_queue_times (adds consultation queue_time).
    May reassign new_service_ids (in the first_fill_qr branch, new_service_ids
    is reduced to additional_service_ids — consultation is excluded).
    Returns (queue_time, new_service_ids) so the orchestrator sees the
    updated list.
    """
    import json
    from datetime import date, datetime

    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.service import Service

    if is_initial_registration:
        # Первичная регистрация - обновляем текущую entry со всеми услугами
        queue_time = entry.queue_time or datetime.now(UTC)
        logger.info(
            "[full_update_online_entry] Первичная регистрация, queue_time: %s",
            queue_time,
        )

    elif is_first_fill_qr:
        # ⭐ FIX 13: Первое заполнение QR-записи
        # ТОЛЬКО ОДНА услуга-консультация (is_consultation=True) получает QR время
        # ВСЕ остальные услуги получают ТЕКУЩЕЕ время и создаются как Independent Queue Entries
        queue_time = entry.queue_time
        logger.info(
            "[full_update_online_entry] ⭐ Первое заполнение QR-записи, queue_time: %s",
            queue_time,
        )

        # ⭐ FIX 13: Ищем РОВНО ОДНУ консультационную услугу
        consultation_service_id = None
        additional_service_ids = []

        for service_item in request.services:
            svc_id = service_item['service_id']
            service = db.query(Service).filter(Service.id == svc_id).first()

            # ⭐ Консультация определяется ТОЛЬКО явным флагом is_consultation
            if service and service.is_consultation and consultation_service_id is None:
                # Первая найденная консультация получает QR время
                consultation_service_id = svc_id
                existing_service_queue_times[svc_id] = (
                    queue_time.isoformat() if hasattr(queue_time, 'isoformat') else str(queue_time)
                )
                logger.info(
                    "[full_update_online_entry] ⭐ FIX 13: Консультация %s (ID=%d) получает QR время: %s",
                    service.name if service else "?",
                    svc_id,
                    queue_time,
                )
            else:
                # Все остальные услуги — дополнительные, получают текущее время
                additional_service_ids.append(svc_id)
                logger.info(
                    "[full_update_online_entry] ⭐ FIX 13: Услуга %s (ID=%d) — дополнительная, получит текущее время",
                    service.name if service else "?",
                    svc_id,
                )

        # ⭐ new_service_ids содержит ТОЛЬКО дополнительные услуги (НЕ консультации)
        # Они будут созданы как Independent Queue Entries с текущим временем
        new_service_ids = additional_service_ids

        logger.info(
            "[full_update_online_entry] ⭐ FIX 13: Консультация ID=%s, Дополнительные услуги (new_service_ids): %s",
            consultation_service_id,
            new_service_ids,
        )

        # ⭐ FIX 13: Создаём Independent Queue Entries для дополнительных услуг
        # Эти услуги получают ТЕКУЩЕЕ время, а не QR время
        # ⭐ FIX 13: Создаём Independent Queue Entries для дополнительных услуг
        # Эти услуги получают ТЕКУЩЕЕ время, а не QR время
        if new_service_ids:
            from zoneinfo import ZoneInfo

            local_tz = ZoneInfo("Asia/Tashkent")
            current_queue_time = datetime.now(local_tz)

            logger.info(
                "[full_update_online_entry] ⭐ FIX 13: Creating %d Independent Queue Entries with current time: %s",
                len(new_service_ids),
                current_queue_time,
            )

            for new_service_id in new_service_ids:
                new_service = db.query(Service).filter(Service.id == new_service_id).first()
                if not new_service:
                    continue

                service_item_data = next(
                    (s for s in request.services if s["service_id"] == new_service_id), None
                )
                _full_update_create_single_independent_entry(
                    db=db,
                    entry=entry,
                    request=request,
                    service=new_service,
                    service_item_data=service_item_data,
                    current_queue_time=current_queue_time,
                )


        # ⭐ FIX 2: Создаём Visit для QR-записи при первом заполнении
        if entry.patient_id and entry.visit_id is None and request.services:
            try:
                from app.services.qr_queue_service import QRQueueService

                qr_service = QRQueueService(db)

                # Подготавливаем услуги для Visit
                services_for_visit = []
                for svc_item in request.services:
                    svc = db.query(Service).filter(Service.id == svc_item['service_id']).first()
                    if svc:
                        services_for_visit.append({
                            'service_id': svc.id,
                            'name': svc.name,
                            'code': svc.code,
                            'price': float(svc.price) if svc.price else 0,
                            'quantity': svc_item.get('quantity', 1),
                        })

                if services_for_visit:
                    visit = qr_service._create_visit_for_qr(
                        patient_id=entry.patient_id,
                        visit_date=date.today(),
                        services=services_for_visit,
                        visit_type=entry.visit_type or "paid",
                        discount_mode=request.discount_mode or "none",
                        notes=f"QR-регистрация: {entry.patient_name}",
                    )
                    entry.visit_id = visit.id
                    logger.info(
                        "[full_update_online_entry] ⭐ FIX 2: Создан Visit ID=%d для QR-записи ID=%d",
                        visit.id, entry.id,
                    )
            except Exception as visit_err:
                logger.warning(
                    "[full_update_online_entry] ⚠️ Не удалось создать Visit для QR-записи: %s",
                    str(visit_err),
                )

    else:
        # Редактирование - обновляем текущую entry ТОЛЬКО со старыми услугами
        # Новые услуги будут добавлены как отдельные entries
        queue_time = entry.queue_time
        logger.info(
            "[full_update_online_entry] Редактирование существующей записи, сохраняем оригинальное queue_time: %s",
            queue_time,
        )

        # ⭐ PHASE 2.2 + FIX 13: Создаём ОТДЕЛЬНЫЕ entries для НОВЫХ/дополнительных услуг
        # Каждая новая услуга получает текущее queue_time и новый номер
        # ⭐ FIX 13: Это теперь работает и для First Fill (дополнительные услуги кроме консультации)
        # ⭐ PHASE 2.2 + FIX 13: Создаём ОТДЕЛЬНЫЕ entries для НОВЫХ/дополнительных услуг
        # Каждая новая услуга получает текущее queue_time и новый номер
        if new_service_ids:
            from zoneinfo import ZoneInfo

            logger.info(
                "[full_update_online_entry] ⭐ Creating %d Independent Queue Entries for additional services",
                len(new_service_ids),
            )

            local_tz = ZoneInfo("Asia/Tashkent")
            current_queue_time = datetime.now(local_tz)

            for new_service_id in new_service_ids:
                new_service = db.query(Service).filter(Service.id == new_service_id).first()
                if not new_service:
                    continue

                service_item_data = next(
                    (s for s in request.services if s["service_id"] == new_service_id), None
                )
                _full_update_create_single_independent_entry(
                    db=db,
                    entry=entry,
                    request=request,
                    service=new_service,
                    service_item_data=service_item_data,
                    current_queue_time=current_queue_time,
                )

            db.flush()  # Сохраняем новые entries



    return queue_time, new_service_ids



def _full_update_update_current_entry_services(
    db: Session,
    entry,
    request,
    existing_service_queue_times: dict,
    new_service_ids: list,
    is_initial_registration: bool,
    is_first_fill_qr: bool,
    queue_time,
):
    """Section 4.5: Populate entry.services / service_codes / total_amount from request.services.

    Skips services already created as Independent Queue Entries (new_service_ids).
    For existing services, preserves original queue_time.
    For new services on initial registration / first-fill, uses registration queue_time.
    For new services on edit, skips (already created as separate entries).

    Mutates entry.services, entry.service_codes, entry.total_amount,
    and entry.queue_time (on initial registration only).
    Returns (services_list, service_codes_list, total_amount).
    """
    import json

    from app.models.service import Service

    services_list = []
    service_codes_list = []
    total_amount = 0

    # ⭐ Обрабатываем услуги для текущей entry
    # При первичной регистрации - добавляем все услуги
    # При редактировании - добавляем только СУЩЕСТВУЮЩИЕ услуги (новые уже созданы как отдельные entries)
    for service_item in request.services:
        service_id = service_item['service_id']

        # ⭐ FIX 13: Пропускаем услуги, которые уже созданы как Independent Queue Entries
        # Это включает:
        # 1. Редактирование: новые услуги (new_service_ids)
        # 2. First Fill: дополнительные услуги (не консультации, тоже в new_service_ids)
        if service_id in new_service_ids:
            logger.info(
                "[full_update_online_entry] ⭐ Пропуск услуги %d — уже создана как Independent Queue Entry",
                service_id,
            )
            continue

        service = db.query(Service).filter(Service.id == service_id).first()
        if service:
            # Рассчитываем стоимость с учетом скидок
            item_price = service.price * service_item.get('quantity', 1)

            logger.info(
                "[full_update_online_entry] Услуга: %s, базовая цена: %s",
                service.name,
                item_price,
            )

            # Применяем скидки
            if service.is_consultation and request.discount_mode in [
                'repeat',
                'benefit',
            ]:
                logger.info(
                    "[full_update_online_entry] Применена скидка на консультацию (%s)",
                    request.discount_mode,
                )
                item_price = 0  # Консультация бесплатна для повторных и льготных

            if request.all_free:
                logger.info("[full_update_online_entry] Применена скидка all_free")
                item_price = 0  # Всё бесплатно

            total_amount += item_price

            # ⭐ FIX PHASE 2: Для существующих услуг используем оригинальное queue_time
            if service_id in existing_service_queue_times:
                service_queue_time = existing_service_queue_times[service_id]
                logger.info(
                    "[full_update_online_entry] ⭐ Сохраняем оригинальное queue_time для %s: %s",
                    service.name,
                    service_queue_time,
                )

                # ✅ НОВОЕ: Создаем полный объект услуги
                service_obj = {
                    "service_id": service.id,
                    "name": service.name,
                    "code": service.service_code
                    or get_service_code(service.id, db)
                    or "UNKNOWN",
                    "quantity": service_item.get('quantity', 1),
                    "price": int(item_price),
                    "queue_time": service_queue_time,  # ⭐ FIX: Используем правильное время
                    "cancelled": False,
                    "cancel_reason": None,
                    "cancelled_by": None,
                    "was_paid_before_cancel": False,
                }
                services_list.append(service_obj)
                service_codes_list.append(
                    service.service_code
                    or get_service_code(service.id, db)
                    or "UNKNOWN"
                )
            else:
                # Новая услуга
                if is_initial_registration or is_first_fill_qr:
                    # Первичная регистрация или первое заполнение QR — время регистрации
                    service_queue_time = (
                        queue_time.isoformat()
                        if hasattr(queue_time, 'isoformat')
                        else str(queue_time)
                    )
                    # Добавляем в services_list ТОЛЬКО для First Fill
                    service_obj = {
                        "service_id": service.id,
                        "name": service.name,
                        "code": service.service_code
                        or get_service_code(service.id, db)
                        or "UNKNOWN",
                        "quantity": service_item.get('quantity', 1),
                        "price": int(item_price),
                        "queue_time": service_queue_time,  # ⭐ FIX: Используем правильное время
                        "cancelled": False,
                        "cancel_reason": None,
                        "cancelled_by": None,
                        "was_paid_before_cancel": False,
                    }
                    services_list.append(service_obj)
                    service_codes_list.append(
                        service.service_code
                        or get_service_code(service.id, db)
                        or "UNKNOWN"
                    )
                else:
                    # ⭐ PHASE 2.2 FIX: Повторное редактирование — Пропускаем добавление в entry.services!
                    # Новые услуги будут созданы как отдельные entries.
                    logger.info(
                        "[full_update_online_entry] ⭐ Пропуск новой услуги %d (уже создана отдельная queue_entry)",
                        service_id
                    )
                    # НЕ добавляем в services_list

    entry.services = json.dumps(services_list, ensure_ascii=False)
    entry.service_codes = json.dumps(
        service_codes_list, ensure_ascii=False
    )  # Обратная совместимость
    entry.total_amount = int(
        total_amount
    )  # ✅ СОХРАНЯЕМ СУММУ (конвертируем в int)

    # ⭐ FIX: При первичной регистрации устанавливаем queue_time на entry
    # Это критически важно! Без этого entry.queue_time остается None,
    # и при следующем редактировании система думает, что это первичная регистрация,
    # перезаписывая queue_time существующих услуг.
    if is_initial_registration and entry.queue_time is None:
        entry.queue_time = queue_time
        logger.info(
            "[full_update_online_entry] ⭐ Установлен queue_time на entry: %s",
            queue_time,
        )

    logger.info(
        "[full_update_online_entry] Услуги обновлены (новый формат): %d услуг(и), Итоговая сумма: %s",
        len(services_list),
        total_amount,
    )

    return services_list, service_codes_list, total_amount



def _full_update_process_services(
    db: Session,
    entry,
    request,
    original_entry_discount_mode: str,
    current_user,
    entry_id: int,
):
    """Section 4: Collect existing services, create new entries, calculate totals."""
    import json
    from datetime import date, datetime

    from app.models.online_queue import DailyQueue, OnlineQueueEntry
    from app.models.patient import Patient
    from app.models.service import Service

    patient_data = request.patient_data
    # ✅ НОВЫЙ ФОРМАТ: Полные объекты услуг с метаданными

    # ⭐ FIX: Определяем существующие услуги из ВСЕХ записей пациента за день (не только текущей entry)
    from datetime import datetime

    from app.models.online_queue import DailyQueue

    existing_service_ids, existing_service_queue_times, final_aggregated_ids = (
        _full_update_collect_existing_services(db=db, entry=entry, request=request)
    )

    # Определяем новые услуги (которые не были в entry.services)
    new_service_ids = []
    for service_item in request.services:
        if service_item['service_id'] not in existing_service_ids:
            new_service_ids.append(service_item['service_id'])

    logger.info(
        "[full_update_online_entry] ⭐ DEBUG: Новые услуги для добавления: %s",
        new_service_ids,
    )
    logger.info(
        "[full_update_online_entry] ⭐ DEBUG: request.services содержит: %s",
        [s['service_id'] for s in request.services],
    )
    logger.info(
        "[full_update_online_entry] ⭐ DEBUG: existing_service_ids: %s",
        list(existing_service_ids),
    )

    # Определяем: это первичная регистрация или редактирование?
    # ⭐ DEBUG: Добавляем логирование для отладки
    logger.info(
        "[full_update_online_entry] DEBUG: entry.queue_time=%s, entry.services=%s (type=%s, len=%s)",
        entry.queue_time,
        entry.services[:100] if entry.services else None,
        type(entry.services).__name__,
        len(entry.services) if entry.services else 0,
    )

    # ⭐ FIX: Улучшенная логика определения первичной регистрации
    # Считаем "первичной регистрацией" ТОЛЬКО если queue_time = None
    # Если есть entry.services (даже пустой JSON []), но queue_time есть - это редактирование
    has_services = False
    if entry.services:
        try:
            parsed = json.loads(entry.services) if isinstance(entry.services, str) else entry.services
            has_services = len(parsed) > 0
        except (json.JSONDecodeError, TypeError):
            has_services = False

    # ⭐ FIX CRITICAL: Улучшенная логика определения первичной регистрации
    # Для QR-записей: если entry.services пустой И мы не нашли услуг в БД для этого пациента — это "первое заполнение"
    # Если услуги в БД найдены (даже если в этой конкретной entry пусто), значит это редактирование (добавление новых)
    is_first_fill_qr = (
        not has_services
        and entry.queue_time is not None
        and entry.source == "online"
        and len(existing_service_ids) == 0  # ⭐ FIX: Только если вообще нет услуг у пациента
    )
    is_initial_registration = entry.queue_time is None

    logger.info(
        "[full_update_online_entry] DEBUG: has_services=%s, is_initial_registration=%s, is_first_fill_qr=%s, source=%s",
        has_services,
        is_initial_registration,
        is_first_fill_qr,
        entry.source,
    )

    queue_time, new_service_ids = _full_update_create_independent_entries(
        db=db,
        entry=entry,
        request=request,
        existing_service_ids=existing_service_ids,
        existing_service_queue_times=existing_service_queue_times,
        is_initial_registration=is_initial_registration,
        is_first_fill_qr=is_first_fill_qr,
        new_service_ids=new_service_ids,
    )

    services_list, service_codes_list, total_amount = (
        _full_update_update_current_entry_services(
            db=db,
            entry=entry,
            request=request,
            existing_service_queue_times=existing_service_queue_times,
            new_service_ids=new_service_ids,
            is_initial_registration=is_initial_registration,
            is_first_fill_qr=is_first_fill_qr,
            queue_time=queue_time,
        )
    )

    # Section 4.6: If all_free, create or update Visit + VisitService records
    visit = _full_update_handle_all_free_visit(
        db=db,
        entry=entry,
        request=request,
        original_entry_discount_mode=original_entry_discount_mode,
        patient_data=patient_data,
        services_list=services_list,
        service_codes_list=service_codes_list,
        total_amount=total_amount,
    )

    return services_list, service_codes_list, total_amount, visit


@router.put("/online-entry/{entry_id}/full-update", response_model=dict[str, Any])
def full_update_online_entry(
    entry_id: int,
    request: FullUpdateOnlineEntryRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist")
    ),
):
    """
    Полное обновление онлайн записи через мастер регистрации:
    - Данные пациента (ФИО, телефон, год рождения, адрес)
    - Тип визита и режим скидки
    - Список услуг
    - Расчет итоговой суммы с учетом скидок
    """
    try:


        logger.info(
            "[full_update_online_entry] Обновление записи ID=%d, Данные пациента: %s, Тип визита: %s, Услуги: %s",
            entry_id,
            request.patient_data,
            request.visit_type,
            request.services,
        )

        # 1-3. Find entry, update patient data, update visit type
        entry, original_entry_discount_mode = _full_update_find_and_validate_entry(
            db, entry_id, current_user
        )
        _full_update_patient_data(entry, request.patient_data)
        _full_update_visit_type(entry, request)

        # 4. Process services: collect existing, create new, calculate totals
        services_list, service_codes_list, total_amount, visit = (
            _full_update_process_services(
                db=db,
                entry=entry,
                request=request,
                original_entry_discount_mode=original_entry_discount_mode,
                current_user=current_user,
                entry_id=entry_id,
            )
        )

        # 5. Finalize: update patient record, handle all_free, build response
        return _full_update_finalize_and_respond(
            db=db,
            entry=entry,
            request=request,
            visit=locals().get('visit'),
            total_amount=total_amount,
            services_list=services_list,
            service_codes_list=service_codes_list,
            original_entry_discount_mode=original_entry_discount_mode,
            current_user=current_user,
            entry_id=entry_id,
            patient_data=request.patient_data,
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "[full_update_online_entry] Ошибка: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

@router.post(
    "/online-entry/{entry_id}/cancel-service", response_model=CancelServiceResponse
)
def cancel_service_in_entry(
    entry_id: int,
    request: CancelServiceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Отменяет услугу в записи очереди с сохранением аудита

    ВАЖНО:
    - Услуга помечается как отмененная (cancelled=True), но НЕ удаляется
    - Сохраняется причина отмены и информация о том, кто отменил
    - Пересчитывается итоговая сумма
    - Если услуга была оплачена, сохраняется флаг was_paid_before_cancel
    - Синхронизируется со всеми другими queue_entries этого пациента

    Доступно: администраторам, регистраторам и врачам
    """
    import json

    from app.models.online_queue import OnlineQueueEntry

    logger.info(
        "[cancel_service] Отмена услуги service_id=%d в entry_id=%d, Причина: %s, Была оплачена: %s, Отменяет: %s (ID: %d)",
        request.service_id,
        entry_id,
        request.cancel_reason,
        request.was_paid,
        current_user.username,
        current_user.id,
    )

    try:
        # Получаем запись
        entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена",
            )

        # Парсим текущие услуги
        _ensure_doctor_can_mutate_queue_entry(
            db,
            entry=entry,
            current_user=current_user,
        )

        services_list = json.loads(entry.services) if entry.services else []

        # Проверяем, что услуги в новом формате (с service_id)
        if not services_list or not isinstance(services_list[0], dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Услуги в старом формате. Необходимо выполнить миграцию данных.",
            )

        # Ищем услугу для отмены
        service_found = False
        cancelled_service_obj = None
        new_total = 0

        for service_obj in services_list:
            if service_obj.get(
                'service_id'
            ) == request.service_id and not service_obj.get('cancelled', False):
                # Отменяем услугу
                service_obj['cancelled'] = True
                service_obj['cancel_reason'] = request.cancel_reason
                service_obj['cancelled_by'] = current_user.id
                service_obj['was_paid_before_cancel'] = request.was_paid
                service_found = True
                cancelled_service_obj = service_obj.copy()
                logger.info(
                    "[cancel_service] Услуга '%s' отменена",
                    service_obj.get('name'),
                )

            # Пересчитываем сумму (только не отмененные услуги)
            if not service_obj.get('cancelled', False):
                new_total += service_obj.get('price', 0) * service_obj.get(
                    'quantity', 1
                )

        if not service_found:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Услуга с ID {request.service_id} не найдена или уже отменена",
            )

        # Обновляем services и total_amount
        entry.services = json.dumps(services_list, ensure_ascii=False)
        entry.total_amount = new_total

        logger.info(
            "[cancel_service] Новая сумма: %s",
            new_total,
        )

        # Sync only within the same visit/session; patient_id alone is too broad.
        if entry.patient_id:
            other_entry_filters = [
                OnlineQueueEntry.patient_id == entry.patient_id,
                OnlineQueueEntry.id != entry.id,
            ]
            if entry.visit_id:
                other_entry_filters.append(OnlineQueueEntry.visit_id == entry.visit_id)
            elif entry.session_id:
                other_entry_filters.extend(
                    [
                        OnlineQueueEntry.visit_id.is_(None),
                        OnlineQueueEntry.session_id == entry.session_id,
                    ]
                )
            else:
                other_entry_filters.extend(
                    [
                        OnlineQueueEntry.visit_id.is_(None),
                        OnlineQueueEntry.queue_id == entry.queue_id,
                    ]
                )

            other_entries = (
                db.query(OnlineQueueEntry)
                .filter(*other_entry_filters)
                .all()
            )

            if other_entries:
                logger.info(
                    "[cancel_service] Синхронизация отмены с %d другими записями",
                    len(other_entries),
                )

                for other_entry in other_entries:
                    other_services = (
                        json.loads(other_entry.services) if other_entry.services else []
                    )

                    # Проверяем формат
                    if other_services and isinstance(other_services[0], dict):
                        other_total = 0
                        updated = False

                        for other_service_obj in other_services:
                            # Отменяем ту же услугу
                            if other_service_obj.get(
                                'service_id'
                            ) == request.service_id and not other_service_obj.get(
                                'cancelled', False
                            ):
                                other_service_obj['cancelled'] = True
                                other_service_obj['cancel_reason'] = (
                                    request.cancel_reason
                                )
                                other_service_obj['cancelled_by'] = current_user.id
                                other_service_obj['was_paid_before_cancel'] = (
                                    request.was_paid
                                )
                                updated = True

                            # Пересчитываем сумму
                            if not other_service_obj.get('cancelled', False):
                                other_total += other_service_obj.get(
                                    'price', 0
                                ) * other_service_obj.get('quantity', 1)

                        if updated:
                            other_entry.services = json.dumps(
                                other_services, ensure_ascii=False
                            )
                            other_entry.total_amount = other_total
                            logger.info(
                                "[cancel_service] Синхронизирована запись %d, новая сумма: %s",
                                other_entry.id,
                                other_total,
                            )

        # Коммитим изменения
        db.commit()
        db.refresh(entry)

        logger.info("[cancel_service] ✅ Услуга успешно отменена")

        return {
            "success": True,
            "message": f"Услуга '{cancelled_service_obj.get('name')}' успешно отменена",
            "cancelled_service": cancelled_service_obj,
            "new_total_amount": new_total,
        }

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()

        logger.error(
            "[cancel_service] Ошибка: %s: %s",
            type(e).__name__,
            str(e),
            exc_info=True,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

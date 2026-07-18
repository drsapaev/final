"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from doctor_integration.py (1900 LOC god file → modular).
"""
from __future__ import annotations

from app.api.v1.endpoints.doctor_integration._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.doctor_integration._helpers import (  # noqa: F401
    DOCTOR_QUEUE_ALLOWED_TAGS,
    DOCTOR_QUEUE_SPECIALTY_VARIANTS,
    ScheduleNextVisitRequest,
    ScheduleNextVisitResponse,
    ScheduleNextVisitService,
    _doctor_queue_action_flags,
    _doctor_queue_available_actions,
    _doctor_schedule_patient_context_exists,
    _ensure_legacy_complete_doctor_access,
    _ensure_schedule_next_patient_access,
    _ensure_visit_doctor_access,
    _normalize_queue_specialty,
    _resolve_queue_allowed_tags,
    _resolve_queue_specialty_variants,
    _serialize_queue_doctor,
    _visit_filter_doctor_id,
    router,
)


@router.get("/doctor/{specialty}/queue/today", response_model=dict[str, Any])
def get_doctor_queue_today(
    specialty: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Получить очередь врача на сегодня
    Из passport.md стр. 1419: GET /api/doctor/cardiology/queue/today
    """
    try:
        normalized_specialty = _normalize_queue_specialty(specialty)
        specialty_variants = _resolve_queue_specialty_variants(normalized_specialty)
        allowed_queue_tags = _resolve_queue_allowed_tags(normalized_specialty)

        doctor = None
        if normalized_specialty == "general":
            doctor = (
                db.query(Doctor)
                .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
                .first()
            )
        else:
            doctor = (
                db.query(Doctor)
                .filter(
                    and_(
                        Doctor.specialty.in_(specialty_variants),
                        Doctor.user_id == current_user.id,
                        Doctor.active == True,
                    )
                )
                .first()
            )

        if not doctor and normalized_specialty != "general":
            doctor = (
                db.query(Doctor)
                .filter(
                    and_(
                        Doctor.specialty.in_(specialty_variants), Doctor.active == True
                    )
                )
                .first()
            )

        if not doctor and normalized_specialty != "general":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Врач специальности '{specialty}' не найден. Проверенные варианты: {specialty_variants}",
            )

        today = date.today()

        candidate_specialist_ids = (
            {doctor.id}
            if doctor
            else ({current_user.id} if normalized_specialty == "general" else set())
        )

        daily_queue_query = db.query(DailyQueue).filter(
            and_(
                DailyQueue.day == today,
                DailyQueue.specialist_id.in_(sorted(candidate_specialist_ids)),
            )
        )

        if allowed_queue_tags:
            queue_tag_filters = [DailyQueue.queue_tag.in_(allowed_queue_tags)]
            if normalized_specialty == "general":
                queue_tag_filters.append(DailyQueue.queue_tag.is_(None))
            daily_queue_query = daily_queue_query.filter(or_(*queue_tag_filters))

        daily_queues = daily_queue_query.order_by(DailyQueue.id.asc()).all()

        if not daily_queues:
            legacy_queue = (
                db.query(DailyQueue)
                .filter(
                    and_(
                        DailyQueue.day == today,
                        DailyQueue.specialist_id.in_(sorted(candidate_specialist_ids)),
                    )
                )
                .order_by(DailyQueue.id.asc())
                .first()
            )
            if legacy_queue and (
                normalized_specialty == "general"
                or legacy_queue.queue_tag in allowed_queue_tags
                or legacy_queue.queue_tag is None
            ):
                daily_queues = [legacy_queue]

        if not daily_queues:
            return {
                "queue_exists": False,
                "doctor": _serialize_queue_doctor(
                    doctor, current_user, normalized_specialty
                ),
                "date": today.isoformat(),
                "entries": [],
                "stats": {"total": 0, "waiting": 0, "called": 0, "served": 0},
                "can_call_next": False,
                "next_call_entry_id": None,
            }

        # Получаем записи очереди
        queue_ids = [queue.id for queue in daily_queues]
        entries = (
            db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.queue_id.in_(queue_ids))
            .order_by(OnlineQueueEntry.queue_id.asc(), OnlineQueueEntry.number.asc())
            .all()
        )

        # Формируем данные для врача
        queue_entries = []
        next_call_entry_id = None
        for entry in entries:
            available_actions = _doctor_queue_available_actions(entry)
            action_flags = _doctor_queue_action_flags(entry)
            if next_call_entry_id is None and action_flags["can_call"]:
                next_call_entry_id = entry.id

            patient_data = None
            if entry.patient:
                patient_data = {
                    "id": entry.patient.id,
                    "first_name": entry.patient.first_name,
                    "last_name": entry.patient.last_name,
                    "middle_name": entry.patient.middle_name,
                    "phone": entry.patient.phone,
                    "birth_date": (
                        entry.patient.birth_date.isoformat()
                        if entry.patient.birth_date
                        else None
                    ),
                }

            queue_entries.append(
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name
                    or (
                        f"{entry.patient.last_name} {entry.patient.first_name}"
                        if entry.patient
                        else "Пациент"
                    ),
                    "phone": entry.phone,
                    "source": entry.source,
                    "status": entry.status,
                    "created_at": entry.created_at.isoformat() if entry.created_at else None,
                    "queue_time": entry.queue_time.isoformat() if entry.queue_time else None,
                    "updated_at": entry.updated_at.isoformat() if entry.updated_at else None,
                    "last_changed_at": entry.updated_at.isoformat() if entry.updated_at else None,
                    "display_time_kind": "queue_time" if entry.queue_time else "created_at",
                    "timezone": "Asia/Tashkent",
                    "called_at": (
                        entry.called_at.isoformat() if entry.called_at else None
                    ),
                    "patient": patient_data,
                    "available_actions": available_actions,
                    **action_flags,
                }
            )

        # Статистика очереди
        stats = {
            "total": len(entries),
            "waiting": len([e for e in entries if e.status == "waiting"]),
            "called": len([e for e in entries if e.status == "called"]),
            "served": len([e for e in entries if e.status == "served"]),
            "online_entries": len([e for e in entries if e.source == "online"]),
            "desk_entries": len([e for e in entries if e.source == "desk"]),
        }

        return {
            "queue_exists": True,
            "queue_id": queue_ids[0],
            "queue_ids": queue_ids,
            "opened_at": (
                daily_queues[0].opened_at.isoformat()
                if daily_queues[0].opened_at
                else None
            ),
            "doctor": _serialize_queue_doctor(doctor, current_user, normalized_specialty),
            "date": today.isoformat(),
            "entries": queue_entries,
            "stats": stats,
            "can_call_next": next_call_entry_id is not None,
            "next_call_entry_id": next_call_entry_id,
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ СТАТУСАМИ ПАЦИЕНТОВ =====================


@router.post("/doctor/queue/{entry_id}/call", response_model=dict[str, Any])
def call_patient(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Вызвать пациента в кабинет
    Из passport.md стр. 1425: POST /api/visits/:id/complete
    """
    try:
        # Получаем запись в очереди
        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )

        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена",
            )

        # Проверяем что врач имеет право работать с этой очередью
        daily_queue = queue_entry.queue

        if not daily_queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Очередь не найдена"
            )

        doctor = daily_queue.specialist

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден для этой очереди",
            )

        # PR-26: Allow any doctor of the same specialty to call patients
        # from this queue. Previously, only the queue owner (doctor.user_id
        # matching current_user.id) could call — which broke when multiple
        # doctors of the same specialty shared a queue.
        # Now: Admin can always call; any doctor can call from queues
        # where the queue's doctor has the same specialty as the caller.
        if current_user.role != "Admin":
            caller_doctor = db.query(Doctor).filter(
                Doctor.user_id == current_user.id,
                Doctor.active == True,
            ).first()

            if not caller_doctor:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Только врач может вызывать пациентов",
                )

            # Allow if caller is the queue owner OR has the same specialty
            if doctor.user_id != current_user.id:
                caller_specialty = (caller_doctor.specialty or "").lower().strip()
                queue_specialty = (doctor.specialty or "").lower().strip()
                if not caller_specialty or not queue_specialty or caller_specialty != queue_specialty:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="Нет прав для работы с этой очередью — вы не владелец и специальность не совпадает",
                    )

        # Обновляем статус на "вызван"
        if "call" not in _doctor_queue_available_actions(queue_entry):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Вызывать можно только waiting, текущий: {queue_entry.status}",
            )

        changed_at = datetime.now(UTC)
        queue_entry.status = "called"
        queue_entry.called_at = changed_at
        queue_entry.updated_at = changed_at

        db.commit()
        db.refresh(queue_entry)

        # Отправляем событие в WebSocket для табло
        try:
            import asyncio

            from app.services.display_websocket import get_display_manager

            async def send_to_display():
                manager = get_display_manager()
                doctor_name = (
                    doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                )
                cabinet = doctor.cabinet

                await manager.broadcast_patient_call(
                    queue_entry=queue_entry, doctor_name=doctor_name, cabinet=cabinet
                )

            # Запускаем асинхронную отправку в фоне
            asyncio.create_task(send_to_display())

        except Exception as ws_error:
            # Не прерываем основной процесс если WebSocket не работает
            logger.warning("Не удалось отправить на табло: %s", ws_error, exc_info=True)

        return {
            "success": True,
            "message": f"Пациент #{queue_entry.number} вызван в кабинет",
            "entry": {
                "id": queue_entry.id,
                "number": queue_entry.number,
                "status": queue_entry.status,
                "called_at": queue_entry.called_at.isoformat(),
                "updated_at": queue_entry.updated_at.isoformat() if queue_entry.updated_at else None,
            },
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/doctor/queue/{entry_id}/start-visit", response_model=dict[str, Any])
def start_patient_visit(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Начать прием пациента (статус в процессе)
    """
    try:
        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )

        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена",
            )

        daily_queue = queue_entry.queue
        doctor = daily_queue.specialist if daily_queue else None
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден для этой очереди",
            )

        # PR-26: same-specialty doctors can also work with this queue
        if current_user.role != "Admin" and doctor.user_id and doctor.user_id != current_user.id:
            caller_doctor = db.query(Doctor).filter(
                Doctor.user_id == current_user.id, Doctor.active == True,
            ).first()
            if not caller_doctor:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                    detail="Только врач может работать с этой очередью")
            caller_specialty = (caller_doctor.specialty or "").lower().strip()
            queue_specialty = (doctor.specialty or "").lower().strip()
            if not caller_specialty or not queue_specialty or caller_specialty != queue_specialty:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет прав для работы с этой очередью")

        # Обновляем статус
        if "start_visit" not in _doctor_queue_available_actions(queue_entry):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    "Start visit is not available for current queue status: "
                    f"{queue_entry.status}"
                ),
            )

        changed_at = datetime.now(UTC)
        queue_entry.status = "in_progress"
        queue_entry.updated_at = changed_at

        # Создаем или обновляем визит в таблице visits
        visit = crud_visit.find_or_create_today_visit(
            db=db,
            patient_id=queue_entry.patient_id,
            doctor_id=doctor.id,
            department=getattr(daily_queue, "queue_tag", None) or "general",
        )

        # Обновляем время начала приема
        visit.visit_time = datetime.now().strftime("%H:%M")
        visit.notes = f"Прием начат в {datetime.now().strftime('%H:%M')}"

        visit.updated_at = changed_at

        db.commit()

        return {
            "success": True,
            "message": "Прием пациента начат",
            "entry_id": entry_id,
            "status": "in_progress",
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.post("/doctor/queue/{entry_id}/complete", response_model=dict[str, Any])
def complete_patient_visit(
    entry_id: int,
    visit_data: CompleteVisitRequest = CompleteVisitRequest(),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "Receptionist",
            "cardio",
            "cardiology",
            "Cardiologist",
            "derma",
            "dentist",
            "Lab",
        )
    ),
):
    """
    Завершить прием пациента
    Из passport.md стр. 1425: POST /api/visits/:id/complete
    """
    try:
        visit_data = visit_data.model_dump(exclude_none=True) if visit_data else {}
        from app.models.appointment import Appointment
        from app.models.online_queue import OnlineQueueEntry
        from app.models.visit import Visit

        # Канонический путь этого endpoint работает по queue_entries.id.
        # Лишь если такой записи в очереди нет, допускаем legacy fallback на Visit/Appointment.
        queue_entry = (
            db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        )
        requested_patient_id = None
        if isinstance(visit_data, dict):
            raw_patient_id = visit_data.get("patient_id")
            try:
                requested_patient_id = (
                    int(raw_patient_id) if raw_patient_id is not None else None
                )
            except (TypeError, ValueError):
                requested_patient_id = None

        if (
            queue_entry
            and requested_patient_id is not None
            and queue_entry.patient_id is not None
            and queue_entry.patient_id != requested_patient_id
        ):
            # Some legacy doctor flows pass appointment/visit IDs to this route.
            # If the numeric ID collides with an unrelated queue entry, do not
            # mutate the queue entry; allow the typed legacy fallback below.
            logger.warning(
                "complete_patient_visit: route id matched a queue entry for a different patient than the request payload; trying legacy record fallback"
            )
            queue_entry = None

        visit = None
        if not queue_entry:
            visit = db.query(Visit).filter(Visit.id == entry_id).first()
            if (
                visit
                and requested_patient_id is not None
                and visit.patient_id is not None
                and visit.patient_id != requested_patient_id
            ):
                logger.warning(
                    "complete_patient_visit: route id matched a Visit for a different patient than the request payload; trying appointment fallback"
                )
                visit = None
        if visit:
            _ensure_legacy_complete_doctor_access(
                db,
                record_doctor_id=visit.doctor_id,
                current_user=current_user,
            )
            # Обновляем статус визита
            visit.status = "completed"
            visit.updated_at = datetime.now(UTC)

            # Payment state remains in Payment; completion must not rewrite
            # registration discount_mode.
            db.commit()
            db.refresh(visit)

            # Завершаем визит с медицинскими данными
            if visit_data:
                crud_visit.complete_visit(
                    db=db, visit_id=visit.id, medical_data=visit_data
                )

            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed",
            }

        # Если не найден в Visit, ищем в Appointment
        appointment = None
        if not queue_entry:
            appointment = (
                db.query(Appointment).filter(Appointment.id == entry_id).first()
            )
            if (
                appointment
                and requested_patient_id is not None
                and appointment.patient_id is not None
                and appointment.patient_id != requested_patient_id
            ):
                logger.warning(
                    "complete_patient_visit: route id matched an Appointment for a different patient than the request payload"
                )
                appointment = None
        if appointment:
            _ensure_legacy_complete_doctor_access(
                db,
                record_doctor_id=appointment.doctor_id,
                current_user=current_user,
            )
            # Обновляем статус appointment
            appointment.status = "completed"

            db.commit()
            db.refresh(appointment)

            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed",
            }

        # Если найден queue entry, завершаем канонический queue flow
        if queue_entry:
            # Проверяем права врача на эту очередь
            daily_queue = queue_entry.queue
            doctor = daily_queue.specialist if daily_queue else None
            if (
                doctor
                and current_user.role != "Admin"
                and doctor.user_id != current_user.id
            ):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет прав для работы с этой очередью",
                )

            # Отмечаем запись очереди как обслуженную
            if "complete" not in _doctor_queue_available_actions(queue_entry):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        "Complete visit is not available for current queue status: "
                        f"{queue_entry.status}"
                    ),
                )

            changed_at = datetime.now(UTC)
            queue_entry.status = "served"
            queue_entry.updated_at = changed_at
            db.commit()
            db.refresh(queue_entry)

            # Создаем или обновляем визит на сегодня и помечаем как завершенный,
            # чтобы это отразилось в registrar/queues/today, который читает Visit/Appointment
            try:
                visit = crud_visit.find_or_create_today_visit(
                    db=db,
                    patient_id=queue_entry.patient_id,
                    doctor_id=doctor.id if doctor else None,
                    department=(
                        daily_queue.department
                        if daily_queue and hasattr(daily_queue, 'department')
                        else "cardiology"
                    ),
                )
                # ✅ Обновляем статус визита на completed
                visit.status = "completed"
                visit.updated_at = changed_at

                # ✅ ИСПРАВЛЕНО: Проверяем и сохраняем информацию об оплате, создаем платеж через SSOT
                # Если визит был оплачен (есть записи в Payment или статус указывает на оплату)
                from app.models.payment import Payment

                payment = (
                    db.query(Payment)
                    .filter(Payment.visit_id == visit.id)
                    .order_by(Payment.created_at.desc())
                    .first()
                )
                payment_is_paid = bool(
                    payment
                    and (
                        (payment.status and payment.status.lower() == "paid")
                        or payment.paid_at
                    )
                )
                if payment_is_paid:
                    # Paid payment may update explicit payment markers only;
                    # registration discount_mode must be preserved.
                    if (
                        hasattr(visit, 'payment_processed_at')
                        and not visit.payment_processed_at
                    ):
                        visit.payment_processed_at = (
                            payment.paid_at or datetime.now(UTC)
                        )
                # ✅ Также обновляем соответствующий Appointment, если он существует
                from app.models.appointment import Appointment

                appointment = (
                    db.query(Appointment)
                    .filter(
                        and_(
                            Appointment.patient_id == queue_entry.patient_id,
                            (
                                Appointment.appointment_date == visit.visit_date
                                if visit.visit_date
                                else date.today()
                            ),
                            Appointment.doctor_id == visit.doctor_id,
                        )
                    )
                    .first()
                )

                if appointment:
                    appointment.status = "completed"
                    # Appointment has no discount_mode; use its explicit payment marker.
                    if (
                        payment_is_paid
                        and not appointment.payment_processed_at
                    ):
                        appointment.payment_processed_at = (
                            payment.paid_at or datetime.now(UTC)
                        )

                if visit_data:
                    # Сохраняем медицинские данные, если переданы
                    crud_visit.complete_visit(
                        db=db, visit_id=visit.id, medical_data=visit_data
                    )

                # ✅ Коммитим все изменения (Visit и Appointment)
                db.commit()
                db.refresh(visit)
                if appointment:
                    db.refresh(appointment)
            except Exception as e:
                # Не блокируем основной флоу очереди, если с визитом что-то пошло не так
                logger.warning(
                    f"Ошибка создания/обновления визита при завершении приема: {e}"
                )
                db.rollback()

            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed",
            }

        # Иначе действительно не найдено
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=t("error.not_found")
        )

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УСЛУГИ ДЛЯ ВРАЧА =====================



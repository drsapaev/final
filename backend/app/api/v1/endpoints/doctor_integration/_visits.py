"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from doctor_integration.py (1900 LOC god file → modular).
"""

from __future__ import annotations

import math  # noqa: F401 — DOCVISIT-BE-002 finite-price validation

from sqlalchemy import text

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
from app.crud.clinic import clinic_today
from app.models.patient import Patient
from app.services.appointment_duration_snapshot import (
    duration_snapshot_for_service_id,
)
from app.services.payment_invariant_service import PaymentInvariantService

# DOCSCHED-BE-001..005 (audit #3892, group 18): the doctor schedule-next
# visit-creation plane. A repeated identical intent inside the dedup
# window replays the ORIGINAL visit/token instead of creating a second
# pending_confirmation visit; the all_free business field is canonical
# (visit, service rows, confirmation and billing agree); the past-date
# check follows the CLINIC's calendar (clinic_today SSOT), not the UTC
# host's date.today(); a non-doctor principal no longer writes its
# users.id into the doctors.id foreign key (unowned visit instead).

# DOCSCHED-BE-001: окно дедупликации повторного schedule-next intent'а.
# Покрывает повтор из-за потерянного HTTP-ответа/двойного нажатия;
# осознанная повторная запись пациента выполняется после истечения окна
# (или с другим intent'ом — время/услуги/скидка) и создаёт новый визит.
_SCHEDULE_NEXT_DEDUP_WINDOW_SECONDS = 10


def _acquire_schedule_next_dedup_lock(
    db: Session, *, patient_id: int, visit_date: date
) -> None:
    """DOCSCHED-BE-001: транзакционный PostgreSQL advisory-lock на intent
    (пациент + дата визита) — сериализует конкурирующие идентичные
    POST'ы между воркерами ДО check-before-write дедупликации (та же
    парадигма, что ``lock_owner_config_scope``/``acquire_phone_scope_lock``).
    SQLite (локальные тесты) advisory-локов не имеет — no-op.
    """
    if db.get_bind().dialect.name != "postgresql":
        return
    db.execute(
        text("SELECT pg_advisory_xact_lock(hashtext(:k))"),
        {"k": f"schedule_next:{patient_id}:{visit_date.isoformat()}"},
    )


def _schedule_next_service_lines_match(
    stored_lines: list[VisitService],
    intended: list[tuple[int, int, float]],
) -> bool:
    """DOCSCHED-BE-001: строки услуг совпадают с intent'ом (multiset по
    (service_id, qty, effective price)) — цена сравнивается допуском на
    копеечные различия float."""
    if len(stored_lines) != len(intended):
        return False
    stored = sorted(
        (line.service_id, line.qty or 0, float(line.price or 0))
        for line in stored_lines
    )
    wanted = sorted(
        (service_id, qty, float(price)) for service_id, qty, price in intended
    )
    return all(
        left[0] == right[0]
        and left[1] == right[1]
        and math.isclose(left[2], right[2], abs_tol=0.01)
        for left, right in zip(stored, wanted, strict=False)
    )


def _find_recent_identical_schedule_next(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int | None,
    visit_date: date,
    visit_time: str | None,
    discount_mode: str,
    notes: str | None,
    service_lines: list[tuple[int, int, float]],
    confirmation_channel: str,
) -> Visit | None:
    """DOCSCHED-BE-001: недавний идентичный pending_confirmation визит.

    Совпадение полного intent'а: пациент, врач (или его отсутствие), дата,
    время, каноничный discount_mode, заметки, все строки услуг с их
    эффективными ценами и канал подтверждения (RETRO-3960-01: канал входит
    в равенство intent'а — replay честен только для повторной отправки ТОГО
    ЖЕ запроса). Возвращённый визит — основа для replay-ответа;
    новый визит и токен подтверждения НЕ создаются.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=_SCHEDULE_NEXT_DEDUP_WINDOW_SECONDS)
    query = (
        db.query(Visit)
        .filter(
            Visit.patient_id == patient_id,
            Visit.visit_date == visit_date,
            Visit.status == "pending_confirmation",
            Visit.discount_mode == discount_mode,
            Visit.created_at >= cutoff,
            # RETRO-3960-01: идентичный replay обязан запрашивать тот же
            # канал подтверждения, что и сохранённый визит.
            Visit.confirmation_channel == confirmation_channel,
        )
    )
    if doctor_id is None:
        query = query.filter(Visit.doctor_id.is_(None))
    else:
        query = query.filter(Visit.doctor_id == doctor_id)
    candidates = query.order_by(Visit.id.desc()).all()
    for candidate in candidates:
        if (candidate.visit_time or None) != (visit_time or None):
            continue
        if (candidate.notes or None) != (notes or None):
            continue
        stored_lines = (
            db.query(VisitService)
            .filter(VisitService.visit_id == candidate.id)
            .all()
        )
        if _schedule_next_service_lines_match(stored_lines, service_lines):
            return candidate
    return None


def _find_recent_channel_mismatch_schedule_next(
    db: Session,
    *,
    patient_id: int,
    doctor_id: int | None,
    visit_date: date,
    visit_time: str | None,
    discount_mode: str,
    notes: str | None,
    service_lines: list[tuple[int, int, float]],
    confirmation_channel: str,
) -> Visit | None:
    """RETRO-3960-01: тот же intent, но с ДРУГИМ каналом подтверждения.

    Возвращает недавний pending_confirmation визит, у которого совпадают
    пациент/врач/дата/время/скидка/заметки/услуги, но сохранённый
    confirmation_channel отличается от запрошенного. Вызов обязан обработать
    такой визит ЯВНО (правдивый конфликт), а не молча дедуплицировать его
    с подменой канала в ответе: сохранённый визит остаётся на исходном
    канале, приглашение на новый канал не отправлялось, и ответ не имеет
    права заявлять новый канал.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=_SCHEDULE_NEXT_DEDUP_WINDOW_SECONDS)
    query = (
        db.query(Visit)
        .filter(
            Visit.patient_id == patient_id,
            Visit.visit_date == visit_date,
            Visit.status == "pending_confirmation",
            Visit.discount_mode == discount_mode,
            Visit.created_at >= cutoff,
            # SQL NULL-семантика: визиты без канала (легаси) не попадают
            # ни в идентичный replay, ни в mismatch — для них поведение
            # не меняется.
            Visit.confirmation_channel != confirmation_channel,
        )
    )
    if doctor_id is None:
        query = query.filter(Visit.doctor_id.is_(None))
    else:
        query = query.filter(Visit.doctor_id == doctor_id)
    candidates = query.order_by(Visit.id.desc()).all()
    for candidate in candidates:
        if (candidate.visit_time or None) != (visit_time or None):
            continue
        if (candidate.notes or None) != (notes or None):
            continue
        stored_lines = (
            db.query(VisitService)
            .filter(VisitService.visit_id == candidate.id)
            .all()
        )
        if _schedule_next_service_lines_match(stored_lines, service_lines):
            return candidate
    return None


def _schedule_next_confirmation_data(
    *,
    visit: Visit,
    patient: Patient,
    channel: str,
    total_amount: float,
    services_count: int,
    notification_sent: bool,
) -> dict[str, Any]:
    """Единая сборка confirmation-блока ответа schedule-next (и для fresh,
    и для DOCSCHED-BE-001 replay-ответа из сохранённого визита)."""
    return {
        "token": visit.confirmation_token,
        "channel": channel,
        "expires_at": (
            visit.confirmation_expires_at.isoformat()
            if visit.confirmation_expires_at
            else None
        ),
        "patient_name": patient.short_name(),
        "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
        "visit_time": visit.visit_time,
        "total_amount": total_amount,
        "services_count": services_count,
        "notification_sent": notification_sent,
    }

# DOCVISIT-BE-001/002/003 (audit #3892, group 17): the doctor-side
# visit-service mutation plane. The persisted ``VisitService.price`` IS the
# effective (custom or catalogue) price — there is no separate custom_price
# column, so responses must not fabricate one; inputs are validated before
# any persistence; and mutations coordinate with the payment ledger (the
# canonical Visit lock, in-flight invoice reservations and net settled
# amounts) instead of silently re-basing paid visits.


def _assert_visit_services_mutable(db: Session, visit_id: int) -> None:
    """DOCVISIT-BE-003: guard visit-service mutations against the payment
    ledger.

    Locks the visit row first (the same ``visits`` → invoice order payment
    flows use), rejects in-flight ``processing`` invoice reservations and
    fails closed when the visit has a net settled amount (paid minus
    completed refunds). Unpaid and fully refunded visits stay mutable.
    """
    invariant = PaymentInvariantService(db)
    invariant.lock_visit_for_payment_change(visit_id)
    net_settled = invariant.compute_paid_amount(visit_id)
    if net_settled > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "Нельзя изменять услуги визита с проведённой оплатой "
                "(оплачено с учётом возвратов: "
                f"{net_settled}). Оформите возврат/пересчёт через кассу."
            ),
        )


def _validate_add_service_inputs(
    *, quantity: int, custom_price: float | None
) -> None:
    """DOCVISIT-BE-002: quantity must be >= 1 and a custom price must be a
    finite non-negative amount. Rejected BEFORE any row is persisted."""
    if quantity < 1:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Количество услуги должно быть не меньше 1",
        )
    if custom_price is not None:
        if not math.isfinite(custom_price) or custom_price < 0:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=(
                    "Цена услуги должна быть неотрицательным конечным числом"
                ),
            )


def _find_recent_identical_add(
    db: Session,
    *,
    visit_id: int,
    service_id: int,
    quantity: int,
    effective_price,
) -> VisitService | None:
    """DOCVISIT-BE-001 retry-idempotency: the immediately preceding identical
    add (same service/quantity/effective price inside the short retry
    window) is treated as a replay of a lost HTTP response, not as a second
    clinical line."""
    cutoff = datetime.now(UTC) - timedelta(seconds=10)
    return (
        db.query(VisitService)
        .filter(
            VisitService.visit_id == visit_id,
            VisitService.service_id == service_id,
            VisitService.qty == quantity,
            VisitService.price == effective_price,
            VisitService.created_at >= cutoff,
        )
        .order_by(VisitService.id.desc())
        .first()
    )


@router.post("/doctor/visits/schedule-next", response_model=ScheduleNextVisitResponse)
async def schedule_next_visit(
    request: ScheduleNextVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """
    Назначение следующего визита врачом (без номера в очереди)
    Номер будет присвоен только после подтверждения пациентом
    """
    try:
        # DOCSCHED-BE-002 follow-up (группа 18): валидация финансовых
        # входов ДО любой персистентности — тот же контракт, что у
        # doctor add-service (DOCVISIT-BE-002), через второй вход.
        for service_req in request.services:
            _validate_add_service_inputs(
                quantity=service_req.quantity,
                custom_price=service_req.custom_price,
            )

        # Получаем врача
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        # DOCSCHED-BE-003: прошедшая дата определяется по календарю
        # КЛИНИКИ (clinic_today SSOT, таймзона настроек очередей), а не по
        # host-UTC date.today(): на UTC-хосте между 19:00 и полночью
        # клинический день Asia/Tashkent уже наступил, и host-проверка
        # пропускала прошедшую для клиники дату.
        if request.visit_date < clinic_today(db):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя назначить визит на прошедшую дату",
            )

        # Проверяем существование пациента
        patient = db.query(Patient).filter(Patient.id == request.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("patient.not_found")
            )

        # Проверяем существование услуг
        _ensure_schedule_next_patient_access(
            db,
            patient_id=request.patient_id,
            doctor=doctor,
            current_user=current_user,
        )

        service_ids = [s.service_id for s in request.services]
        services = db.query(Service).filter(Service.id.in_(service_ids)).all()

        if len(services) != len(service_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некоторые услуги не найдены",
            )

        # DOCSCHED-BE-002: канонизация бизнес-поля. discount_mode='all_free'
        # и all_free=True — ОДИН и тот же intent: все строки нулевые, визит
        # хранит discount_mode='all_free'. Прежний код принимал
        # mode='all_free' при ненулевых ценах (режим «все бесплатно» с
        # каталоговыми суммами в подтверждении и биллинге).
        effective_all_free = request.all_free or request.discount_mode == "all_free"
        normalized_discount_mode = (
            "all_free" if effective_all_free else request.discount_mode
        )

        # Вычисляем эффективные строки услуг ЗАРАНЕЕ: они нужны и для
        # DOCSCHED-BE-001 дедупликации intent'а, и для создания визита.
        services_by_id = {service.id: service for service in services}
        intended_lines: list[tuple[int, int, float]] = []
        for service_req in request.services:
            service = services_by_id[service_req.service_id]

            # DOCSCHED-BE-002 follow-up: явный custom_price=0 — осознанная
            # бесплатная цена, а не falsy-fallback на каталог.
            if service_req.custom_price is not None:
                service_price = float(service_req.custom_price)
            else:
                service_price = float(service.price) if service.price else 0

            # Применяем скидки для консультаций
            if service.is_consultation:
                if request.discount_mode in ["repeat", "benefit"] or effective_all_free:
                    service_price = 0

            # All Free делает всё бесплатным
            if effective_all_free:
                service_price = 0

            intended_lines.append((service.id, service_req.quantity, service_price))

        # DOCSCHED-BE-001: идемпотентность уровня операции. Повторный
        # идентичный intent (потерянный HTTP-ответ, двойное нажатие) в
        # окне дедупликации возвращает ИСХОДНЫЙ визит и токен — второй
        # pending_confirmation визит не создаётся. Advisory-lock
        # сериализует конкурирующие воркеры до check-before-write.
        _acquire_schedule_next_dedup_lock(
            db, patient_id=request.patient_id, visit_date=request.visit_date
        )
        replay_visit = _find_recent_identical_schedule_next(
            db,
            patient_id=request.patient_id,
            doctor_id=doctor.id if doctor else None,
            visit_date=request.visit_date,
            visit_time=request.visit_time,
            discount_mode=normalized_discount_mode,
            notes=request.notes,
            service_lines=intended_lines,
            confirmation_channel=request.confirmation_channel,
        )
        # RETRO-3960-01 (post-merge review 3968): the same terms but a
        # DIFFERENT confirmation channel is NOT an identical replay. It must
        # never be silently deduplicated into a response that claims the
        # requested channel: the persisted visit keeps the ORIGINAL channel
        # and no invitation was sent to the new one. Handle it explicitly
        # with a truthful conflict instead.
        channel_mismatch_visit = (
            None
            if replay_visit is not None
            else _find_recent_channel_mismatch_schedule_next(
                db,
                patient_id=request.patient_id,
                doctor_id=doctor.id if doctor else None,
                visit_date=request.visit_date,
                visit_time=request.visit_time,
                discount_mode=normalized_discount_mode,
                notes=request.notes,
                service_lines=intended_lines,
                confirmation_channel=request.confirmation_channel,
            )
        )
        if channel_mismatch_visit is not None:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    "Недавняя заявка на этот же визит уже ожидает подтверждения "
                    f"по каналу «{channel_mismatch_visit.confirmation_channel}». "
                    f"Запрошенный канал «{request.confirmation_channel}» не применён: "
                    "визит сохранён на исходном канале и приглашение на новый канал "
                    "не отправлялось. Отмените существующую заявку или повторите "
                    "после закрытия окна дедупликации."
                ),
            )
        if replay_visit is not None:
            stored_lines = (
                db.query(VisitService)
                .filter(VisitService.visit_id == replay_visit.id)
                .all()
            )
            replay_total = sum(
                float(line.price or 0) * (line.qty or 0) for line in stored_lines
            )
            confirmation_data = _schedule_next_confirmation_data(
                visit=replay_visit,
                patient=patient,
                channel=request.confirmation_channel,
                total_amount=replay_total,
                services_count=len(stored_lines),
                # Приглашение уже отправлено исходным запросом (результат
                # недоступен replay'у) — не заявляем доставку, которой не
                # видели, и не спамим пациента повторной отправкой.
                notification_sent=False,
            )
            return ScheduleNextVisitResponse(
                success=True,
                message=(
                    "Визит уже создан этим же запросом — повторная отправка "
                    "не создала второй визит и не повторила приглашение."
                ),
                visit_id=replay_visit.id,
                status="pending_confirmation",
                confirmation=confirmation_data,
                idempotent_replay=True,
            )

        # Генерируем токен подтверждения
        confirmation_token = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(
            hours=48
        )  # 48 часов на подтверждение

        # Создаем визит со статусом pending_confirmation
        # DOCSCHED-BE-004: doctor_id — это doctors.id (FK), а НЕ users.id.
        # Прежний fallback «doctor_id=current_user.id» для персонала без
        # профиля врача писал users.id в FK: на PostgreSQL — IntegrityError
        # (500), а при числовом совпадении с чужим Doctor.id — тихая
        # привязка визита к постороннему врачу. Визит без врача —
        # поддерживаемое состояние (выдача номера падает fail-closed по
        # D-08, решение за оператором).
        visit = Visit(
            patient_id=request.patient_id,
            doctor_id=doctor.id if doctor else None,
            visit_date=request.visit_date,
            visit_time=request.visit_time,
            status="pending_confirmation",  # Ожидает подтверждения
            discount_mode=normalized_discount_mode,
            department="mixed",  # Будет определен по услугам
            notes=request.notes,
            confirmation_token=confirmation_token,
            confirmation_channel=request.confirmation_channel,
            confirmation_expires_at=expires_at,
            source="desk",  # ✅ SSOT: Врач назначает = desk
        )
        db.add(visit)
        db.flush()  # Получаем ID визита

        # Добавляем услуги к визиту
        total_amount = 0
        for service_id, quantity, service_price in intended_lines:
            service = services_by_id[service_id]
            visit_service = VisitService(
                visit_id=visit.id,
                service_id=service.id,
                duration_minutes_snapshot=duration_snapshot_for_service_id(
                    db, service.id, doctor_id=visit.doctor_id
                ),
                name=service.name,
                # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                code=service.service_code or get_service_code(service.id, db),
                qty=quantity,
                price=service_price,
                currency="UZS",
            )
            db.add(visit_service)

            total_amount += service_price * quantity

        db.commit()
        db.refresh(visit)

        # Отправляем приглашение на подтверждение
        notification_service = NotificationService(db)
        try:
            # Signature contract: send_visit_confirmation_invitation(db,
            # visit_id, channel). The previous kwargs call (visit=visit,
            # channel=...) raised TypeError on EVERY schedule-next visit and
            # was swallowed below — invitations never reached patients.
            notification_result = (
                await notification_service.send_visit_confirmation_invitation(
                    db, visit.id, request.confirmation_channel
                )
            )
            # PII/security (Codex P1): the pwa channel returns a URL with
            # the RAW confirmation token — never log the full result dict.
            logger.info(
                "Приглашение отправлено для визита %s: channel=%s success=%s",
                visit.id,
                notification_result.get("channel"),
                notification_result.get("success"),
            )
        except Exception as e:
            logger.error(f"Ошибка отправки приглашения для визита {visit.id}: {e}")
            # Не прерываем выполнение, визит уже создан

        # Формируем ответ
        confirmation_data = _schedule_next_confirmation_data(
            visit=visit,
            patient=patient,
            channel=request.confirmation_channel,
            total_amount=total_amount,
            services_count=len(request.services),
            notification_sent=(
                notification_result.get("success", False)
                if "notification_result" in locals()
                else False
            ),
        )

        return ScheduleNextVisitResponse(
            success=True,
            message=f"Визит назначен на {request.visit_date}. Ожидает подтверждения пациентом.",
            visit_id=visit.id,
            status="pending_confirmation",
            confirmation=confirmation_data,
            idempotent_replay=False,
        )

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка назначения следующего визита: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== УПРАВЛЕНИЕ ВИЗИТАМИ =====================


@router.get("/doctor/visits/today", response_model=dict[str, Any])
def get_today_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """Получить сегодняшние визиты врача"""
    try:
        visits = crud_visit.get_today_visits_by_doctor(
            db=db,
            doctor_id=_visit_filter_doctor_id(db, current_user),
        )

        result = []
        for visit in visits:
            # Получаем услуги визита
            visit_services = crud_visit.get_visit_services(db=db, visit_id=visit.id)

            services_data = []
            total_amount = 0

            for vs in visit_services:
                service = db.query(Service).filter(Service.id == vs.service_id).first()
                service_data = {
                    "id": vs.id,
                    "service_id": vs.service_id,
                    "service_name": (
                        service.name if service else f"Услуга #{vs.service_id}"
                    ),
                    "quantity": vs.quantity,
                    "price": vs.price,
                    "total": vs.price * vs.quantity,
                }
                services_data.append(service_data)
                total_amount += service_data["total"]

            result.append(
                {
                    "id": visit.id,
                    "patient_id": visit.patient_id,
                    "visit_date": (
                        visit.visit_date.isoformat() if visit.visit_date else None
                    ),
                    "visit_time": visit.visit_time,
                    "status": visit.status,
                    "department": visit.department,
                    "discount_mode": visit.discount_mode,
                    "notes": visit.notes,
                    "services": services_data,
                    "total_amount": total_amount,
                    "created_at": (
                        visit.created_at.isoformat() if visit.created_at else None
                    ),
                }
            )

        return {"success": True, "visits": result, "total_count": len(result)}

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/doctor/visits/statistics", response_model=dict[str, Any])
def get_visit_statistics(
    date_from: str | None = Query(None, description="Дата начала в формате YYYY-MM-DD"),
    date_to: str | None = Query(
        None, description="Дата окончания в формате YYYY-MM-DD"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Получить статистику визитов врача"""
    try:
        from datetime import datetime

        date_from_obj = None
        date_to_obj = None

        if date_from:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()

        if date_to:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()

        stats = crud_visit.get_visit_statistics(
            db=db,
            doctor_id=_visit_filter_doctor_id(db, current_user),
            date_from=date_from_obj,
            date_to=date_to_obj,
        )

        return {
            "success": True,
            "statistics": stats,
            "period": {"date_from": date_from, "date_to": date_to},
        }

    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.get("/doctor/visits/{visit_id}", response_model=dict[str, Any])
def get_visit_details(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin",
            "Doctor",
            "Registrar",
            "Cashier",
            "cardio",
            "cardiology",
            "derma",
            "dentist",
        )
    ),
):
    """Получить детали визита"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Получаем услуги визита
        visit_services = crud_visit.get_visit_services(db=db, visit_id=visit.id)

        services_data = []
        total_amount = 0

        for vs in visit_services:
            service = db.query(Service).filter(Service.id == vs.service_id).first()
            service_data = {
                "id": vs.id,
                "service_id": vs.service_id,
                "service_name": service.name if service else f"Услуга #{vs.service_id}",
                "service_code": (
                    (service.service_code or get_service_code(service.id, db))
                    if service
                    else None
                ),
                "quantity": vs.quantity,
                "price": vs.price,
                "total": vs.price * vs.quantity,
            }
            services_data.append(service_data)
            total_amount += service_data["total"]

        return {
            "success": True,
            "visit": {
                "id": visit.id,
                "patient_id": visit.patient_id,
                "doctor_id": visit.doctor_id,
                "visit_date": (
                    visit.visit_date.isoformat() if visit.visit_date else None
                ),
                "visit_time": visit.visit_time,
                "status": visit.status,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "approval_status": visit.approval_status,
                "notes": visit.notes,
                "services": services_data,
                "total_amount": total_amount,
                "created_at": (
                    visit.created_at.isoformat() if visit.created_at else None
                ),
                "confirmed_at": (
                    visit.confirmed_at.isoformat() if visit.confirmed_at else None
                ),
            },
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.put("/doctor/visits/{visit_id}/add-service", response_model=dict[str, Any])
def add_service_to_visit(
    visit_id: int,
    service_id: int,
    quantity: int = 1,
    custom_price: float | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Добавить услугу к визиту.

    DOCVISIT-BE-002: ``quantity``/``custom_price`` валидируются ДО записи —
    некорректные строки не попадают в биллинг. DOCVISIT-BE-003: мутация
    координируется с платёжным легером (каноничный Visit-lock + отказ при
    processing-инвойсах и оплаченном остатке). DOCVISIT-BE-001: ответ
    строится ТОЛЬКО из персистентного состояния — ``price`` и есть
    фактическая цена (кастомная или каталожная), фантомного ``custom_price``
    поля не существует.
    """
    try:
        # DOCVISIT-BE-002: fail BEFORE any persistence.
        _validate_add_service_inputs(quantity=quantity, custom_price=custom_price)

        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Проверяем, что услуга существует
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Услуга не найдена"
            )

        # DOCVISIT-BE-003: the mutation must respect the payment ledger.
        _assert_visit_services_mutable(db, visit_id)

        # DOCVISIT-BE-001 retry-idempotency: an exact repeat of the
        # immediately preceding add is a replay of a lost response, not a
        # second clinical line.
        effective_price = (
            custom_price if custom_price is not None else (service.price or 0)
        )
        replayed = _find_recent_identical_add(
            db,
            visit_id=visit_id,
            service_id=service_id,
            quantity=quantity,
            effective_price=effective_price,
        )
        if replayed is not None:
            return {
                "success": True,
                "message": "Услуга уже добавлена к визиту (повтор запроса)",
                "idempotent_replay": True,
                "visit_service": {
                    "id": replayed.id,
                    "service_id": replayed.service_id,
                    "service_name": service.name,
                    "quantity": replayed.quantity,
                    "price": replayed.price,
                    "total": replayed.price * replayed.quantity,
                },
            }

        # Добавляем услугу
        visit_service = crud_visit.add_visit_service(
            db=db,
            visit_id=visit_id,
            service_id=service_id,
            quantity=quantity,
            custom_price=custom_price,
        )

        return {
            "success": True,
            "message": "Услуга добавлена к визиту",
            "idempotent_replay": False,
            "visit_service": {
                "id": visit_service.id,
                "service_id": visit_service.service_id,
                "service_name": service.name,
                "quantity": visit_service.quantity,
                "price": visit_service.price,
                "total": visit_service.price * visit_service.quantity,
            },
        }

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


@router.delete(
    "/doctor/visits/{visit_id}/services/{visit_service_id}",
    response_model=dict[str, Any],
)
def remove_service_from_visit(
    visit_id: int,
    visit_service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Удалить услугу из визита.

    DOCVISIT-BE-003: удаление строки услуги оплаченного визита меняет базу
    стоимости под неизменным чеком — отказ (409), как и для добавления.
    """
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)

        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail=t("visit.not_found")
            )

        # Проверяем права доступа
        _ensure_visit_doctor_access(visit, current_user)

        # Удаляем услугу
        visit_service = (
            db.query(VisitService)
            .filter(
                VisitService.id == visit_service_id,
                VisitService.visit_id == visit.id,
            )
            .first()
        )

        if not visit_service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Услуга в визите не найдена",
            )

        # DOCVISIT-BE-003: coordinate with the payment ledger before the
        # destructive mutation.
        _assert_visit_services_mutable(db, visit_id)

        db.delete(visit_service)
        db.commit()

        return {"success": True, "message": "Услуга удалена из визита"}

    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )

"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from doctor_integration.py (1900 LOC god file → modular).
"""

from __future__ import annotations

import math  # noqa: F401 — DOCVISIT-BE-002 finite-price validation

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
from app.services.appointment_duration_snapshot import (
    duration_snapshot_for_service_id,
)
from app.services.payment_invariant_service import PaymentInvariantService

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

        # Проверяем что дата не в прошлом
        if request.visit_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя назначить визит на прошедшую дату",
            )

        # Проверяем существование пациента
        from app.models.patient import Patient

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

        # Генерируем токен подтверждения
        confirmation_token = str(uuid.uuid4())
        expires_at = datetime.now(UTC) + timedelta(
            hours=48
        )  # 48 часов на подтверждение

        # Создаем визит со статусом pending_confirmation
        visit = Visit(
            patient_id=request.patient_id,
            # Backward compatibility for admin/test flows without Doctor profile.
            doctor_id=doctor.id if doctor else current_user.id,
            visit_date=request.visit_date,
            visit_time=request.visit_time,
            status="pending_confirmation",  # Ожидает подтверждения
            discount_mode=request.discount_mode,
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
        for service_req in request.services:
            service = next(s for s in services if s.id == service_req.service_id)

            # Вычисляем цену
            service_price = service_req.custom_price or (
                float(service.price) if service.price else 0
            )

            # Применяем скидки для консультаций
            if service.is_consultation:
                if request.discount_mode in ["repeat", "benefit"] or request.all_free:
                    service_price = 0

            # All Free делает всё бесплатным
            if request.all_free:
                service_price = 0

            visit_service = VisitService(
                visit_id=visit.id,
                service_id=service.id,
                duration_minutes_snapshot=duration_snapshot_for_service_id(
                    db, service.id, doctor_id=visit.doctor_id
                ),
                name=service.name,
                # ✅ SSOT: Используем service_mapping.get_service_code() вместо дублирующей логики
                code=service.service_code or get_service_code(service.id, db),
                qty=service_req.quantity,
                price=service_price,
                currency="UZS",
            )
            db.add(visit_service)

            total_amount += service_price * service_req.quantity

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
        confirmation_data = {
            "token": confirmation_token,
            "channel": request.confirmation_channel,
            "expires_at": expires_at.isoformat(),
            "patient_name": patient.short_name(),
            "visit_date": request.visit_date.isoformat(),
            "visit_time": request.visit_time,
            "total_amount": total_amount,
            "services_count": len(request.services),
            "notification_sent": (
                notification_result.get("success", False)
                if "notification_result" in locals()
                else False
            ),
        }

        return ScheduleNextVisitResponse(
            success=True,
            message=f"Визит назначен на {request.visit_date}. Ожидает подтверждения пациентом.",
            visit_id=visit.id,
            status="pending_confirmation",
            confirmation=confirmation_data,
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

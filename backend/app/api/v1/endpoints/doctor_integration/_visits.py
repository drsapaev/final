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
            "Receptionist",
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
            notification_result = (
                await notification_service.send_visit_confirmation_invitation(
                    visit=visit, channel=request.confirmation_channel
                )
            )
            logger.info(
                f"Приглашение отправлено для визита {visit.id}: {notification_result}"
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
                if 'notification_result' in locals()
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
            "Receptionist",
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
                    "custom_price": vs.custom_price,
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
    date_from: str | None = Query(
        None, description="Дата начала в формате YYYY-MM-DD"
    ),
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

    except HTTPException:
        raise
    except Exception:  # noqa: B025  # manual-review: duplicate exception in try block — manual review
        db.rollback()
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
            "Receptionist",
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
                "service_code": (service.service_code or get_service_code(service.id, db)) if service else None,
                "quantity": vs.quantity,
                "price": vs.price,
                "custom_price": vs.custom_price,
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
    """Добавить услугу к визиту"""
    try:
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
            "visit_service": {
                "id": visit_service.id,
                "service_id": visit_service.service_id,
                "service_name": service.name,
                "quantity": visit_service.quantity,
                "price": visit_service.price,
                "custom_price": visit_service.custom_price,
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


@router.delete("/doctor/visits/{visit_id}/services/{visit_service_id}", response_model=dict[str, Any])
def remove_service_from_visit(
    visit_id: int,
    visit_service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist")
    ),
):
    """Удалить услугу из визита"""
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



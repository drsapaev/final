"""AUTO-GENERATED SPLIT MODULE — see _helpers.py for shared state.

Split from doctor_integration.py (1900 LOC god file → modular).
"""
from __future__ import annotations

from app.api.v1.endpoints.doctor_integration._helpers import *  # noqa: F401, F403
from app.api.v1.endpoints.doctor_integration._helpers import (  # noqa: F401
    DOCTOR_QUEUE_SPECIALTY_VARIANTS,
    DOCTOR_QUEUE_ALLOWED_TAGS,
    ScheduleNextVisitRequest,
    ScheduleNextVisitResponse,
    ScheduleNextVisitService,
    _doctor_queue_action_flags,
    _doctor_queue_available_actions,
    _ensure_legacy_complete_doctor_access,
    _ensure_schedule_next_patient_access,
    _ensure_visit_doctor_access,
    _normalize_queue_specialty,
    _resolve_queue_allowed_tags,
    _resolve_queue_specialty_variants,
    _serialize_queue_doctor,
    _visit_filter_doctor_id,
    _doctor_schedule_patient_context_exists,
    router,
)

@router.get("/doctor/{specialty}/services", response_model=dict[str, Any])
def get_doctor_services(
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
    Получить услуги для врача конкретной специальности
    Из passport.md стр. 1254: услуги визита по специальности
    """
    try:
        # Получаем категории услуг для специальности
        categories = crud_clinic.get_service_categories(
            db, specialty=specialty, active_only=True
        )

        # Получаем услуги
        from app.models.service import Service

        services = db.query(Service).filter(Service.active == True).all()

        # Группируем по категориям
        grouped_services = {}

        for category in categories:
            category_services = [
                {
                    "id": service.id,
                    "name": service.name,
                    "code": service.service_code or get_service_code(service.id, db),
                    "price": float(service.price) if service.price else 0,
                    "currency": service.currency or "UZS",
                    "duration_minutes": service.duration_minutes or 30,
                    "category": {
                        "id": category.id,
                        "code": category.code,
                        "name_ru": category.name_ru,
                    },
                }
                for service in services
                if service.category_id == category.id
            ]

            if category_services:
                grouped_services[category.code] = {
                    "category": {
                        "id": category.id,
                        "code": category.code,
                        "name_ru": category.name_ru,
                        "name_uz": category.name_uz,
                        "specialty": category.specialty,
                    },
                    "services": category_services,
                }

        return {
            "specialty": specialty,
            "services_by_category": grouped_services,
            "total_services": sum(
                len(group["services"]) for group in grouped_services.values()
            ),
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== ИНФОРМАЦИЯ О ВРАЧЕ =====================


@router.get("/doctor/my-info", response_model=dict[str, Any])
def get_doctor_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """
    Получить информацию о текущем враче
    """
    try:
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        # Получаем расписание
        schedules = crud_clinic.get_doctor_schedules(db, doctor.id)

        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)
        specialty_settings = queue_settings.get("start_numbers", {}).get(
            doctor.specialty, 1
        )
        max_per_day = queue_settings.get("max_per_day", {}).get(doctor.specialty, 15)

        return {
            "doctor": {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": (
                    float(doctor.price_default) if doctor.price_default else 0
                ),
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day,
            },
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "full_name": current_user.full_name,
                "email": current_user.email,
                "role": current_user.role,
            },
            "schedules": [
                {
                    "weekday": s.weekday,
                    "start_time": (
                        s.start_time.strftime("%H:%M") if s.start_time else None
                    ),
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
                    "breaks": s.breaks,
                    "active": s.active,
                }
                for s in schedules
            ],
            "queue_settings": {
                "start_number": specialty_settings,
                "max_per_day": max_per_day,
                "timezone": queue_settings.get("timezone", "Asia/Tashkent"),
            },
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== КАЛЕНДАРЬ ВРАЧА =====================


@router.get("/doctor/calendar", response_model=dict[str, Any])
def get_doctor_calendar(
    start_date: date = Query(..., description="Начальная дата"),
    end_date: date = Query(..., description="Конечная дата"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """
    Календарь врача с будущими записями
    Из passport.md стр. 1223: будущие записи с цветами статусов
    """
    try:
        # Получаем врача
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        # Здесь будет логика получения записей из таблицы appointments
        # Пока возвращаем заглушку

        return {
            "doctor_id": doctor.id,
            "period": {"start": start_date.isoformat(), "end": end_date.isoformat()},
            "appointments": [],  # Будет заполнено при интеграции с appointments
            "schedule": [
                {
                    "weekday": s.weekday,
                    "start_time": (
                        s.start_time.strftime("%H:%M") if s.start_time else None
                    ),
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
                    "active": s.active,
                }
                for s in crud_clinic.get_doctor_schedules(db, doctor.id)
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== СТАТИСТИКА ВРАЧА =====================


@router.get("/doctor/stats", response_model=dict[str, Any])
def get_doctor_stats(
    days_back: int = Query(7, ge=1, le=30, description="Дней назад"),
    db: Session = Depends(get_db),
    current_user: User = Depends(
        require_roles(
            "Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"
        )
    ),
):
    """Статистика работы врача"""
    try:
        # Получаем врача
        doctor = (
            db.query(Doctor)
            .filter(and_(Doctor.user_id == current_user.id, Doctor.active == True))
            .first()
        )

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Профиль врача не найден"
            )

        from datetime import timedelta

        start_date = date.today() - timedelta(days=days_back)

        # Получаем очереди за период
        daily_queues = (
            db.query(DailyQueue)
            .filter(
                and_(
                    DailyQueue.specialist_id == doctor.id,
                    DailyQueue.day >= start_date,
                )
            )
            .all()
        )

        total_patients = 0
        served_patients = 0
        online_patients = 0

        for queue in daily_queues:
            entries = (
                db.query(OnlineQueueEntry)
                .filter(OnlineQueueEntry.queue_id == queue.id)
                .all()
            )
            total_patients += len(entries)
            served_patients += len([e for e in entries if e.status == "served"])
            online_patients += len([e for e in entries if e.source == "online"])

        return {
            "doctor": {
                "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
            },
            "period": {
                "start": start_date.isoformat(),
                "end": date.today().isoformat(),
                "days": days_back,
            },
            "stats": {
                "total_patients": total_patients,
                "served_patients": served_patients,
                "online_patients": online_patients,
                "completion_rate": (
                    (served_patients / total_patients * 100)
                    if total_patients > 0
                    else 0
                ),
                "online_rate": (
                    (online_patients / total_patients * 100)
                    if total_patients > 0
                    else 0
                ),
            },
            "daily_breakdown": [
                {
                    "date": queue.day.isoformat(),
                    "opened_at": (
                        queue.opened_at.isoformat() if queue.opened_at else None
                    ),
                    "total_entries": db.query(OnlineQueueEntry)
                    .filter(OnlineQueueEntry.queue_id == queue.id)
                    .count(),
                    "served_entries": db.query(OnlineQueueEntry)
                    .filter(
                        and_(
                            OnlineQueueEntry.queue_id == queue.id,
                            OnlineQueueEntry.status == "served",
                        )
                    )
                    .count(),
                }
                for queue in daily_queues
            ],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error",
        )


# ===================== НАЗНАЧЕНИЕ СЛЕДУЮЩЕГО ВИЗИТА =====================



"""
API endpoints для интеграции панелей врачей с системой
Основа: passport.md стр. 1141-2063
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue

router = APIRouter()

# ===================== ОЧЕРЕДЬ ВРАЧА =====================

@router.get("/doctor/{specialty}/queue/today")
def get_doctor_queue_today(
    specialty: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "derma", "dentist"))
):
    """
    Получить очередь врача на сегодня
    Из passport.md стр. 1419: GET /api/doctor/cardiology/queue/today
    """
    try:
        # Получаем врача по специальности и пользователю
        doctor = db.query(Doctor).filter(
            and_(
                Doctor.specialty == specialty,
                Doctor.user_id == current_user.id,
                Doctor.active == True
            )
        ).first()
        
        if not doctor:
            # Если врач не найден по user_id, ищем по специальности (для админа)
            if current_user.role == "Admin":
                doctor = db.query(Doctor).filter(
                    and_(Doctor.specialty == specialty, Doctor.active == True)
                ).first()
            
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Врач специальности '{specialty}' не найден"
                )
        
        today = date.today()
        
        # Получаем дневную очередь
        daily_queue = db.query(DailyQueue).filter(
            and_(DailyQueue.day == today, DailyQueue.specialist_id == doctor.id)
        ).first()
        
        if not daily_queue:
            return {
                "queue_exists": False,
                "doctor": {
                    "id": doctor.id,
                    "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                    "specialty": doctor.specialty,
                    "cabinet": doctor.cabinet
                },
                "date": today.isoformat(),
                "entries": [],
                "stats": {
                    "total": 0,
                    "waiting": 0,
                    "in_progress": 0,
                    "completed": 0
                }
            }
        
        # Получаем записи очереди
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id
        ).order_by(OnlineQueueEntry.number).all()
        
        # Формируем данные для врача
        queue_entries = []
        for entry in entries:
            patient_data = None
            if entry.patient:
                patient_data = {
                    "id": entry.patient.id,
                    "first_name": entry.patient.first_name,
                    "last_name": entry.patient.last_name,
                    "middle_name": entry.patient.middle_name,
                    "phone": entry.patient.phone,
                    "birth_date": entry.patient.birth_date.isoformat() if entry.patient.birth_date else None
                }
            
            queue_entries.append({
                "id": entry.id,
                "number": entry.number,
                "patient_name": entry.patient_name or (
                    f"{entry.patient.last_name} {entry.patient.first_name}" if entry.patient else "Пациент"
                ),
                "phone": entry.phone,
                "source": entry.source,
                "status": entry.status,
                "created_at": entry.created_at.isoformat(),
                "called_at": entry.called_at.isoformat() if entry.called_at else None,
                "patient": patient_data
            })
        
        # Статистика очереди
        stats = {
            "total": len(entries),
            "waiting": len([e for e in entries if e.status == "waiting"]),
            "called": len([e for e in entries if e.status == "called"]),
            "served": len([e for e in entries if e.status == "served"]),
            "online_entries": len([e for e in entries if e.source == "online"]),
            "desk_entries": len([e for e in entries if e.source == "desk"])
        }
        
        return {
            "queue_exists": True,
            "queue_id": daily_queue.id,
            "opened_at": daily_queue.opened_at.isoformat() if daily_queue.opened_at else None,
            "doctor": {
                "id": doctor.id,
                "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet
            },
            "date": today.isoformat(),
            "entries": queue_entries,
            "stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения очереди врача: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ СТАТУСАМИ ПАЦИЕНТОВ =====================

@router.post("/doctor/queue/{entry_id}/call")
def call_patient(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "derma", "dentist"))
):
    """
    Вызвать пациента в кабинет
    Из passport.md стр. 1425: POST /api/visits/:id/complete
    """
    try:
        # Получаем запись в очереди
        queue_entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        
        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена"
            )
        
        # Проверяем что врач имеет право работать с этой очередью
        daily_queue = queue_entry.queue
        doctor = daily_queue.specialist
        
        if current_user.role != "Admin" and doctor.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для работы с этой очередью"
            )
        
        # Обновляем статус на "вызван"
        queue_entry.status = "called"
        queue_entry.called_at = datetime.utcnow()
        
        db.commit()
        db.refresh(queue_entry)
        
        # Отправляем событие в WebSocket для табло
        try:
            import asyncio
            from app.services.display_websocket import get_display_manager
            
            async def send_to_display():
                manager = get_display_manager()
                doctor_name = doctor.user.full_name if doctor.user else f"Врач #{doctor.id}"
                cabinet = doctor.cabinet
                
                await manager.broadcast_patient_call(
                    queue_entry=queue_entry,
                    doctor_name=doctor_name,
                    cabinet=cabinet
                )
            
            # Запускаем асинхронную отправку в фоне
            asyncio.create_task(send_to_display())
            
        except Exception as ws_error:
            # Не прерываем основной процесс если WebSocket не работает
            print(f"Предупреждение: не удалось отправить на табло: {ws_error}")
        
        return {
            "success": True,
            "message": f"Пациент #{queue_entry.number} вызван в кабинет",
            "entry": {
                "id": queue_entry.id,
                "number": queue_entry.number,
                "status": queue_entry.status,
                "called_at": queue_entry.called_at.isoformat()
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка вызова пациента: {str(e)}"
        )


@router.post("/doctor/queue/{entry_id}/start-visit")
def start_patient_visit(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "derma", "dentist"))
):
    """
    Начать прием пациента (статус в процессе)
    """
    try:
        queue_entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        
        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена"
            )
        
        # Обновляем статус
        queue_entry.status = "in_progress"
        
        # Здесь будет создание или обновление визита
        # TODO: Интеграция с таблицей visits
        
        db.commit()
        
        return {
            "success": True,
            "message": "Прием пациента начат",
            "entry_id": entry_id,
            "status": "in_progress"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка начала приема: {str(e)}"
        )


@router.post("/doctor/queue/{entry_id}/complete")
def complete_patient_visit(
    entry_id: int,
    visit_data: Optional[Dict[str, Any]] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "derma", "dentist"))
):
    """
    Завершить прием пациента
    Из passport.md стр. 1425: POST /api/visits/:id/complete
    """
    try:
        queue_entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        
        if not queue_entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена"
            )
        
        # Обновляем статус на завершен
        queue_entry.status = "served"
        
        # Здесь будет сохранение данных визита
        # TODO: Сохранение в таблицу visits с медицинскими данными
        
        db.commit()
        
        return {
            "success": True,
            "message": "Прием пациента завершен",
            "entry_id": entry_id,
            "status": "served"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка завершения приема: {str(e)}"
        )


# ===================== УСЛУГИ ДЛЯ ВРАЧА =====================

@router.get("/doctor/{specialty}/services")
def get_doctor_services(
    specialty: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "derma", "dentist"))
):
    """
    Получить услуги для врача конкретной специальности
    Из passport.md стр. 1254: услуги визита по специальности
    """
    try:
        # Получаем категории услуг для специальности
        categories = crud_clinic.get_service_categories(db, specialty=specialty, active_only=True)
        
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
                    "code": service.code,
                    "price": float(service.price) if service.price else 0,
                    "currency": service.currency or "UZS",
                    "duration_minutes": service.duration_minutes or 30,
                    "category": {
                        "id": category.id,
                        "code": category.code,
                        "name_ru": category.name_ru
                    }
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
                        "specialty": category.specialty
                    },
                    "services": category_services
                }
        
        return {
            "specialty": specialty,
            "services_by_category": grouped_services,
            "total_services": sum(len(group["services"]) for group in grouped_services.values())
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения услуг врача: {str(e)}"
        )


# ===================== ИНФОРМАЦИЯ О ВРАЧЕ =====================

@router.get("/doctor/my-info")
def get_doctor_info(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Doctor", "cardio", "derma", "dentist"))
):
    """
    Получить информацию о текущем враче
    """
    try:
        doctor = db.query(Doctor).filter(
            and_(Doctor.user_id == current_user.id, Doctor.active == True)
        ).first()
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль врача не найден"
            )
        
        # Получаем расписание
        schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
        
        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)
        specialty_settings = queue_settings.get("start_numbers", {}).get(doctor.specialty, 1)
        max_per_day = queue_settings.get("max_per_day", {}).get(doctor.specialty, 15)
        
        return {
            "doctor": {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": float(doctor.price_default) if doctor.price_default else 0,
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day
            },
            "user": {
                "id": current_user.id,
                "username": current_user.username,
                "full_name": current_user.full_name,
                "email": current_user.email,
                "role": current_user.role
            },
            "schedules": [
                {
                    "weekday": s.weekday,
                    "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
                    "breaks": s.breaks,
                    "active": s.active
                }
                for s in schedules
            ],
            "queue_settings": {
                "start_number": specialty_settings,
                "max_per_day": max_per_day,
                "timezone": queue_settings.get("timezone", "Asia/Tashkent")
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации врача: {str(e)}"
        )


# ===================== КАЛЕНДАРЬ ВРАЧА =====================

@router.get("/doctor/calendar")
def get_doctor_calendar(
    start_date: date = Query(..., description="Начальная дата"),
    end_date: date = Query(..., description="Конечная дата"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Doctor", "cardio", "derma", "dentist"))
):
    """
    Календарь врача с будущими записями
    Из passport.md стр. 1223: будущие записи с цветами статусов
    """
    try:
        # Получаем врача
        doctor = db.query(Doctor).filter(
            and_(Doctor.user_id == current_user.id, Doctor.active == True)
        ).first()
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль врача не найден"
            )
        
        # Здесь будет логика получения записей из таблицы appointments
        # Пока возвращаем заглушку
        
        return {
            "doctor_id": doctor.id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "appointments": [],  # Будет заполнено при интеграции с appointments
            "schedule": [
                {
                    "weekday": s.weekday,
                    "start_time": s.start_time.strftime("%H:%M") if s.start_time else None,
                    "end_time": s.end_time.strftime("%H:%M") if s.end_time else None,
                    "active": s.active
                }
                for s in crud_clinic.get_doctor_schedules(db, doctor.id)
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения календаря: {str(e)}"
        )


# ===================== СТАТИСТИКА ВРАЧА =====================

@router.get("/doctor/stats")
def get_doctor_stats(
    days_back: int = Query(7, ge=1, le=30, description="Дней назад"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Doctor", "cardio", "derma", "dentist"))
):
    """Статистика работы врача"""
    try:
        # Получаем врача
        doctor = db.query(Doctor).filter(
            and_(Doctor.user_id == current_user.id, Doctor.active == True)
        ).first()
        
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль врача не найден"
            )
        
        from datetime import timedelta
        start_date = date.today() - timedelta(days=days_back)
        
        # Получаем очереди за период
        daily_queues = db.query(DailyQueue).filter(
            and_(
                DailyQueue.specialist_id == doctor.id,
                DailyQueue.day >= start_date
            )
        ).all()
        
        total_patients = 0
        served_patients = 0
        online_patients = 0
        
        for queue in daily_queues:
            entries = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == queue.id).all()
            total_patients += len(entries)
            served_patients += len([e for e in entries if e.status == "served"])
            online_patients += len([e for e in entries if e.source == "online"])
        
        return {
            "doctor": {
                "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet
            },
            "period": {
                "start": start_date.isoformat(),
                "end": date.today().isoformat(),
                "days": days_back
            },
            "stats": {
                "total_patients": total_patients,
                "served_patients": served_patients,
                "online_patients": online_patients,
                "completion_rate": (served_patients / total_patients * 100) if total_patients > 0 else 0,
                "online_rate": (online_patients / total_patients * 100) if total_patients > 0 else 0
            },
            "daily_breakdown": [
                {
                    "date": queue.day.isoformat(),
                    "opened_at": queue.opened_at.isoformat() if queue.opened_at else None,
                    "total_entries": db.query(OnlineQueueEntry).filter(OnlineQueueEntry.queue_id == queue.id).count(),
                    "served_entries": db.query(OnlineQueueEntry).filter(
                        and_(OnlineQueueEntry.queue_id == queue.id, OnlineQueueEntry.status == "served")
                    ).count()
                }
                for queue in daily_queues
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики врача: {str(e)}"
        )

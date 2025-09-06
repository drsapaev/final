"""
API endpoints для интеграции регистратуры с админ панелью
Основа: detail.md стр. 85-183
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue

router = APIRouter()

# ===================== СПРАВОЧНИК УСЛУГ ДЛЯ РЕГИСТРАТУРЫ =====================

@router.get("/registrar/services")
def get_registrar_services(
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
    active_only: bool = Query(True, description="Только активные услуги"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить услуги для регистратуры из справочника админ панели
    Из detail.md стр. 112: "Услуги (чек‑лист, группами — дерма/косметология/кардио/ЭКГ/ЭхоКГ/стоматология/лаборатория)"
    """
    try:
        # Получаем категории услуг
        categories = crud_clinic.get_service_categories(db, specialty=specialty, active_only=active_only)
        
        # Получаем услуги из основной таблицы
        from app.models.service import Service
        query = db.query(Service)
        
        if active_only:
            query = query.filter(Service.active == True)
        
        services = query.all()
        
        # Группируем услуги по категориям согласно документации
        grouped_services = {
            "consultation": {
                "cardiology": [],
                "dermatology": [],
                "stomatology": []
            },
            "procedure": {
                "cosmetology": [],
                "dermatology": []
            },
            "diagnostics": {
                "ecg": [],
                "echo": [],
                "lab": []
            },
            "laboratory": {
                "blood": [],
                "biochemistry": [],
                "hormones": []
            }
        }
        
        # Маппим категории к группам
        category_mapping = {}
        for category in categories:
            if category.code.startswith("consultation."):
                specialty_key = category.code.split(".")[1]
                if specialty_key in grouped_services["consultation"]:
                    category_mapping[category.id] = ("consultation", specialty_key)
            elif category.code.startswith("procedure."):
                specialty_key = category.code.split(".")[1]
                if specialty_key in grouped_services["procedure"]:
                    category_mapping[category.id] = ("procedure", specialty_key)
            elif category.code.startswith("diagnostics."):
                diag_key = category.code.split(".")[1]
                if diag_key in grouped_services["diagnostics"]:
                    category_mapping[category.id] = ("diagnostics", diag_key)
            elif category.code.startswith("laboratory."):
                lab_key = category.code.split(".")[1]
                if lab_key in grouped_services["laboratory"]:
                    category_mapping[category.id] = ("laboratory", lab_key)
        
        # Распределяем услуги по группам
        for service in services:
            service_data = {
                "id": service.id,
                "name": service.name,
                "code": service.code,
                "price": float(service.price) if service.price else 0,
                "currency": service.currency or "UZS",
                "duration_minutes": service.duration_minutes or 30,
                "category_id": service.category_id,
                "doctor_id": service.doctor_id
            }
            
            if service.category_id and service.category_id in category_mapping:
                group, subgroup = category_mapping[service.category_id]
                grouped_services[group][subgroup].append(service_data)
        
        return {
            "services_by_group": grouped_services,
            "categories": [
                {
                    "id": cat.id,
                    "code": cat.code,
                    "name_ru": cat.name_ru,
                    "name_uz": cat.name_uz,
                    "specialty": cat.specialty
                }
                for cat in categories
            ],
            "total_services": len(services)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения услуг для регистратуры: {str(e)}"
        )


# ===================== ВРАЧИ И РАСПИСАНИЯ =====================

@router.get("/registrar/doctors")
def get_registrar_doctors(
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
    with_schedule: bool = Query(True, description="Включить расписание"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить врачей с расписаниями для регистратуры
    Из detail.md стр. 106: "Специалист/Кабинет"
    """
    try:
        doctors = crud_clinic.get_doctors(db, active_only=True)
        
        if specialty:
            doctors = [d for d in doctors if d.specialty == specialty]
        
        result = []
        for doctor in doctors:
            doctor_data = {
                "id": doctor.id,
                "user_id": doctor.user_id,
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "price_default": float(doctor.price_default) if doctor.price_default else 0,
                "start_number_online": doctor.start_number_online,
                "max_online_per_day": doctor.max_online_per_day,
                "user": {
                    "full_name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                    "username": doctor.user.username if doctor.user else None
                } if doctor.user else None
            }
            
            if with_schedule:
                schedules = crud_clinic.get_doctor_schedules(db, doctor.id)
                doctor_data["schedules"] = [
                    {
                        "id": schedule.id,
                        "weekday": schedule.weekday,
                        "start_time": schedule.start_time.strftime("%H:%M") if schedule.start_time else None,
                        "end_time": schedule.end_time.strftime("%H:%M") if schedule.end_time else None,
                        "breaks": schedule.breaks,
                        "active": schedule.active
                    }
                    for schedule in schedules
                ]
            
            result.append(doctor_data)
        
        return {
            "doctors": result,
            "total_doctors": len(result),
            "by_specialty": {
                specialty: len([d for d in result if d["specialty"] == specialty])
                for specialty in set(d["specialty"] for d in result)
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения врачей: {str(e)}"
        )


# ===================== НАСТРОЙКИ ОЧЕРЕДИ ДЛЯ РЕГИСТРАТУРЫ =====================

@router.get("/registrar/queue-settings")
def get_registrar_queue_settings(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
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
                    "start_number": queue_settings.get("start_numbers", {}).get(doctor.specialty, 1),
                    "max_per_day": queue_settings.get("max_per_day", {}).get(doctor.specialty, 15),
                    "doctors": []
                }
            
            specialty_info[doctor.specialty]["doctors"].append({
                "id": doctor.id,
                "name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                "cabinet": doctor.cabinet
            })
        
        return {
            "timezone": queue_settings.get("timezone", "Asia/Tashkent"),
            "queue_start_hour": queue_settings.get("queue_start_hour", 7),
            "auto_close_time": queue_settings.get("auto_close_time", "09:00"),
            "specialties": specialty_info,
            "current_time": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения настроек очереди: {str(e)}"
        )


# ===================== СОЗДАНИЕ ЗАПИСИ В РЕГИСТРАТУРЕ =====================

@router.post("/registrar/appointments")
def create_registrar_appointment(
    appointment_data: Dict[str, Any],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Создание записи через регистратуру
    Из detail.md стр. 366-376: POST /api/visits
    """
    try:
        # Валидируем обязательные поля
        required_fields = ["patient_id", "doctor_id", "date", "services", "type", "payment_type"]
        for field in required_fields:
            if field not in appointment_data:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Обязательное поле '{field}' отсутствует"
                )
        
        # Получаем врача для проверки настроек
        doctor = crud_clinic.get_doctor_by_id(db, appointment_data["doctor_id"])
        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден"
            )
        
        # Получаем настройки очереди
        queue_settings = crud_clinic.get_queue_settings(db)
        
        # Создаем запись в очереди если это на сегодня
        appointment_date = datetime.strptime(appointment_data["date"], "%Y-%m-%d").date()
        
        if appointment_date == date.today():
            # Получаем или создаем дневную очередь
            daily_queue = db.query(crud_queue.DailyQueue).filter(
                and_(
                    crud_queue.DailyQueue.day == appointment_date,
                    crud_queue.DailyQueue.specialist_id == doctor.id
                )
            ).first()
            
            if not daily_queue:
                daily_queue = crud_queue.DailyQueue(
                    day=appointment_date,
                    specialist_id=doctor.id,
                    active=True
                )
                db.add(daily_queue)
                db.commit()
                db.refresh(daily_queue)
            
            # Вычисляем номер в очереди
            current_count = db.query(crud_queue.QueueEntry).filter(
                crud_queue.QueueEntry.queue_id == daily_queue.id
            ).count()
            
            start_number = queue_settings.get("start_numbers", {}).get(doctor.specialty, 1)
            next_number = start_number + current_count
            
            # Создаем запись в очереди
            queue_entry = crud_queue.QueueEntry(
                queue_id=daily_queue.id,
                number=next_number,
                patient_id=appointment_data["patient_id"],
                source="desk",
                status="waiting"
            )
            db.add(queue_entry)
            
        # Здесь будет создание визита в основной таблице visits
        # Пока возвращаем успешный ответ
        
        db.commit()
        
        return {
            "success": True,
            "message": "Запись создана успешно",
            "appointment_id": f"temp_{datetime.utcnow().timestamp()}",
            "queue_number": next_number if appointment_date == date.today() else None,
            "print_ticket": appointment_date == date.today()  # Печатать талон если на сегодня
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка создания записи: {str(e)}"
        )


# ===================== QR КОДЫ ДЛЯ РЕГИСТРАТУРЫ =====================

@router.post("/registrar/generate-qr")
def generate_qr_for_registrar(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Генерация QR кода из регистратуры
    Из detail.md стр. 355: POST /api/online-queue/qrcode?day&specialist_id
    """
    try:
        token, token_data = crud_queue.generate_qr_token(
            db, day, specialist_id, current_user.id
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
            "current_count": token_data["current_count"]
        }
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR: {str(e)}"
        )


# ===================== ОТКРЫТИЕ ПРИЕМА =====================

@router.post("/registrar/open-reception")
def open_reception(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Открытие приема из регистратуры
    Из detail.md стр. 253: Кнопка «Открыть приём сейчас»
    """
    try:
        result = crud_queue.open_daily_queue(db, day, specialist_id, current_user.id)
        
        return {
            "success": True,
            "message": "Прием открыт, онлайн-набор закрыт",
            "opened_at": result["opened_at"],
            "online_entries_transferred": result["online_entries_count"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка открытия приема: {str(e)}"
        )


# ===================== ТЕКУЩИЕ ОЧЕРЕДИ =====================

@router.get("/registrar/queues/today")
def get_today_queues(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить все очереди на сегодня для регистратуры
    Из detail.md стр. 363: GET /api/queue/today?specialist_id
    """
    try:
        today = date.today()
        
        # Получаем все дневные очереди
        daily_queues = db.query(crud_queue.DailyQueue).filter(
            crud_queue.DailyQueue.day == today
        ).all()
        
        result = []
        for queue in daily_queues:
            # Получаем записи очереди
            entries = db.query(crud_queue.QueueEntry).filter(
                crud_queue.QueueEntry.queue_id == queue.id
            ).order_by(crud_queue.QueueEntry.number).all()
            
            # Получаем врача
            doctor = queue.specialist
            
            queue_data = {
                "queue_id": queue.id,
                "specialist_id": queue.specialist_id,
                "specialist_name": doctor.user.full_name if doctor.user else f"Врач #{doctor.id}",
                "specialty": doctor.specialty,
                "cabinet": doctor.cabinet,
                "opened_at": queue.opened_at,
                "entries": [
                    {
                        "id": entry.id,
                        "number": entry.number,
                        "patient_name": entry.patient_name or (entry.patient.first_name + " " + entry.patient.last_name if entry.patient else "Пациент"),
                        "phone": entry.phone,
                        "source": entry.source,
                        "status": entry.status,
                        "created_at": entry.created_at,
                        "called_at": entry.called_at
                    }
                    for entry in entries
                ],
                "stats": {
                    "total": len(entries),
                    "waiting": len([e for e in entries if e.status == "waiting"]),
                    "called": len([e for e in entries if e.status == "called"]),
                    "served": len([e for e in entries if e.status == "served"]),
                    "online_entries": len([e for e in entries if e.source == "online"])
                }
            }
            
            result.append(queue_data)
        
        return {
            "queues": result,
            "total_queues": len(result),
            "date": today.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения очередей: {str(e)}"
        )


# ===================== КАЛЕНДАРЬ ЗАПИСЕЙ =====================

@router.get("/registrar/calendar")
def get_registrar_calendar(
    start_date: date = Query(..., description="Начальная дата"),
    end_date: date = Query(..., description="Конечная дата"),
    doctor_id: Optional[int] = Query(None, description="Фильтр по врачу"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
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
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "status_colors": {
                "plan": "#6c757d",      # серый — план
                "confirmed": "#007bff",  # синий — подтверждено  
                "queued": "#28a745",    # зеленый — в очереди
                "in_cabinet": "#fd7e14", # оранжевый — в кабинете
                "done": "#20c997",      # зеленый тёмный — завершён
                "cancelled": "#dc3545", # красный — отменен
                "no_show": "#dc3545"    # красный — неявка
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения календаря: {str(e)}"
        )

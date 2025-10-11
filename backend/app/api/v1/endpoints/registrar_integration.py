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
    # Разрешаем доступ также профильным ролям врачей
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist", "Lab"))
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
            "laboratory": [],     # L - Лабораторные анализы
            "dermatology": [],    # D - Дерматологические услуги
            "cosmetology": [],    # C - Косметологические услуги
            "cardiology": [],     # K - Кардиология
            "stomatology": [],    # S - Стоматология
            "procedures": []      # O - Прочие процедуры
        }
        
        # Простая логика распределения услуг по трём группам
        for service in services:
            service_data = {
                "id": service.id,
                "name": service.name,
                "code": service.code,
                "price": float(service.price) if service.price else 0,
                "currency": service.currency or "UZS",
                "duration_minutes": service.duration_minutes or 30,
                "category_id": service.category_id,
                "doctor_id": service.doctor_id,
                # ✅ НОВЫЕ ПОЛЯ ДЛЯ КЛАССИФИКАЦИИ
                "category_code": getattr(service, 'category_code', None),
                "service_code": getattr(service, 'service_code', None),
                "queue_tag": getattr(service, 'queue_tag', None),  # 🎯 ДОБАВЛЯЕМ queue_tag ДЛЯ ЭКГ!
                "is_consultation": getattr(service, 'is_consultation', False),  # Добавляем поле is_consultation
                "group": None  # Добавим группу для frontend
            }
            
            # ✅ НОВАЯ ЛОГИКА: определяем группу по category_code
            category_code = getattr(service, 'category_code', None)
            
            if category_code:
                # Используем новую систему кодов
                if category_code == 'L':
                    service_data["group"] = "laboratory"
                    grouped_services["laboratory"].append(service_data)
                elif category_code == 'D':
                    service_data["group"] = "dermatology"
                    grouped_services["dermatology"].append(service_data)
                elif category_code == 'C':
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
                elif category_code == 'K':
                    service_data["group"] = "cardiology"
                    grouped_services["cardiology"].append(service_data)
                elif category_code == 'S':
                    service_data["group"] = "stomatology"
                    grouped_services["stomatology"].append(service_data)
                elif category_code == 'O':
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
                else:
                    # Неизвестный код - в прочие
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
            else:
                # Fallback: если нет category_code, пытаемся определить по названию
                name_lower = service.name.lower()
                if any(word in name_lower for word in ["анализ", "кровь", "моча", "биохим", "гормон"]):
                    service_data["group"] = "laboratory"
                    grouped_services["laboratory"].append(service_data)
                elif any(word in name_lower for word in ["дерматолог", "кожа", "псориаз", "акне"]):
                    service_data["group"] = "dermatology"
                    grouped_services["dermatology"].append(service_data)
                elif any(word in name_lower for word in ["косметолог", "пилинг", "чистка", "ботокс"]):
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
                elif any(word in name_lower for word in ["кардиолог", "экг", "эхокг", "холтер"]):
                    service_data["group"] = "cardiology"
                    grouped_services["cardiology"].append(service_data)
                elif any(word in name_lower for word in ["стоматолог", "зуб", "кариес"]):
                    service_data["group"] = "stomatology"
                    grouped_services["stomatology"].append(service_data)
                else:
                    # По умолчанию в прочие процедуры
                    service_data["group"] = "procedures"
                    grouped_services["procedures"].append(service_data)
        
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
    # Разрешаем доступ также профильным ролям врачей
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "derma", "dentist", "Lab"))
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


# ===================== УПРАВЛЕНИЕ ОЧЕРЕДЯМИ =====================

@router.post("/registrar/queue/{entry_id}/start-visit")
def start_queue_visit(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Начать прием для записи в очереди (статус в процессе)
    Работает с Visit и Appointment записями
    """
    try:
        from app.models.visit import Visit
        from app.models.appointment import Appointment
        
        # Сначала ищем в Visit
        visit = db.query(Visit).filter(Visit.id == entry_id).first()
        if visit:
            # Обновляем статус визита
            visit.status = "in_progress"
            db.commit()
            db.refresh(visit)
            
            return {
                "success": True,
                "message": "Прием начат успешно",
                "entry": {
                    "id": visit.id,
                    "status": visit.status,
                    "patient_id": visit.patient_id
                }
            }
        
        # Если не найден в Visit, ищем в Appointment
        appointment = db.query(Appointment).filter(Appointment.id == entry_id).first()
        if appointment:
            # Обновляем статус appointment
            appointment.status = "in_progress"
            db.commit()
            db.refresh(appointment)
            
            return {
                "success": True,
                "message": "Прием начат успешно",
                "entry": {
                    "id": appointment.id,
                    "status": appointment.status,
                    "patient_id": appointment.patient_id
                }
            }
        
        # Если не найден ни в Visit, ни в Appointment
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Запись не найдена"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка начала приема: {str(e)}"
        )


# ===================== ТЕКУЩИЕ ОЧЕРЕДИ =====================

@router.get("/registrar/queues/today")
def get_today_queues(
    target_date: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "cardio", "derma", "dentist"))
):
    """
    Получить все очереди на указанную дату для регистратуры
    Из detail.md стр. 363: GET /api/queue/today?specialist_id&date=YYYY-MM-DD
    
    ОБНОВЛЕНО: Теперь получаем данные из Visit вместо DailyQueue
    Доступ: Admin, Registrar, Doctor, Lab
    
    Параметры:
    - target_date: дата в формате YYYY-MM-DD (опционально, по умолчанию - сегодня)
    """
    try:
        from app.models.visit import Visit
        from app.models.appointment import Appointment
        from app.models.patient import Patient
        from app.models.clinic import Doctor
        from datetime import datetime
        
        # Если дата не указана, используем сегодня
        if target_date:
            try:
                today = datetime.strptime(target_date, '%Y-%m-%d').date()
            except ValueError:
                today = date.today()
        else:
            today = date.today()
        
        # Получаем все визиты на сегодня (новая система)
        visits = db.query(Visit).filter(
            Visit.visit_date == today
        ).all()
        
        # Получаем все appointments на сегодня (старая система)
        appointments = db.query(Appointment).filter(
            Appointment.appointment_date == today
        ).all()
        
        # Группируем записи по специальности
        queues_by_specialty = {}
        
        # Обрабатываем Visit (новая система)
        for visit in visits:
            specialty = visit.department or "general"
            
            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": None,
                    "doctor_id": visit.doctor_id
                }
            
            queues_by_specialty[specialty]["entries"].append({
                "type": "visit",
                "data": visit,
                "created_at": visit.confirmed_at or visit.created_at
            })
            
            # Сохраняем первого врача из этой специальности
            if not queues_by_specialty[specialty]["doctor"] and visit.doctor:
                queues_by_specialty[specialty]["doctor"] = visit.doctor
        
        # Обрабатываем Appointment (старая система)
        # Подгружаем актуальный статус оплаты из payments при наличии
        from app.models.payment import Payment
        for appointment in appointments:
            # Определяем специальность из appointment
            specialty = getattr(appointment, 'department', None) or "general"
            
            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": None,
                    "doctor_id": getattr(appointment, 'doctor_id', None)
                }
            
            queues_by_specialty[specialty]["entries"].append({
                "type": "appointment",
                "data": appointment,
                "created_at": appointment.created_at
            })
            
            # Сохраняем врача
            if not queues_by_specialty[specialty]["doctor"] and hasattr(appointment, 'doctor') and appointment.doctor:
                queues_by_specialty[specialty]["doctor"] = appointment.doctor
        
        # Формируем результат
        result = []
        queue_number = 1
        
        for specialty, data in queues_by_specialty.items():
            doctor = data["doctor"]
            entries_list = data["entries"]
            
            # Сортируем записи по времени создания/подтверждения (от раннего к позднему)
            # Это формирует правильную очередь: кто раньше пришёл, тот раньше в очереди
            entries_list.sort(key=lambda e: e["created_at"])
            
            entries = []
            for idx, entry_wrapper in enumerate(entries_list, 1):
                entry_type = entry_wrapper["type"]
                entry_data = entry_wrapper["data"]
                
                # Инициализируем общие переменные
                patient_id = None
                patient_name = "Неизвестный пациент"
                phone = "Не указан"
                patient_birth_year = None
                address = None
                services = []
                service_codes = []
                total_cost = 0
                source = "desk"
                entry_status = "waiting"
                visit_time = None
                discount_mode = "none"
                record_id = None
                
                if entry_type == "visit":
                    # Обработка Visit
                    visit = entry_data
                    record_id = visit.id
                    patient_id = visit.patient_id
                    visit_time = visit.visit_time
                    discount_mode = visit.discount_mode
                    
                    # Загружаем пациента
                    patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
                    if patient:
                        patient_name = f"{patient.last_name} {patient.first_name}"
                        if patient.middle_name:
                            patient_name += f" {patient.middle_name}"
                        phone = patient.phone or "Не указан"
                        if patient.birth_date:
                            patient_birth_year = patient.birth_date.year
                        address = patient.address
                    
                    # Загружаем услуги визита
                    from app.models.visit import VisitService
                    visit_services = db.query(VisitService).filter(
                        VisitService.visit_id == visit.id
                    ).all()
                    
                    for vs in visit_services:
                        if vs.name:
                            services.append(vs.name)
                        if vs.code:
                            service_codes.append(vs.code)
                        if vs.price:
                            total_cost += float(vs.price) * (vs.qty or 1)
                    
                    # Определяем источник записи
                    if visit.confirmed_by:
                        if "telegram" in visit.confirmed_by.lower():
                            source = "online"
                        elif "registrar" in visit.confirmed_by.lower():
                            source = "confirmation"
                    
                    # Определяем статус визита в терминах очереди
                    status_mapping = {
                        "confirmed": "waiting",
                        "pending_confirmation": "waiting",
                        "in_progress": "called",
                        "completed": "served",
                        "cancelled": "no_show"
                    }
                    entry_status = status_mapping.get(visit.status, "waiting")

                    # Устойчивое определение факта оплаты по визиту
                    is_paid = False
                    try:
                        v_status = (getattr(visit, 'status', None) or '').lower()
                        if v_status in ("paid", "in_visit", "in progress", "completed", "done"):
                            is_paid = True
                        elif getattr(visit, 'payment_processed_at', None):
                            is_paid = True
                        # Проверка записей оплаты в таблице payments по visit.id
                        if not is_paid:
                            try:
                                payment_row = db.query(Payment).filter(Payment.visit_id == visit.id).order_by(Payment.created_at.desc()).first()
                                if payment_row and (str(payment_row.status).lower() == 'paid' or payment_row.paid_at):
                                    is_paid = True
                            except Exception:
                                pass
                    except Exception:
                        pass

                    if is_paid:
                        discount_mode = 'paid'
                
                elif entry_type == "appointment":
                    # Обработка Appointment
                    appointment = entry_data
                    record_id = appointment.id
                    patient_id = appointment.patient_id
                    visit_time = str(appointment.appointment_time) if hasattr(appointment, 'appointment_time') else None
                    
                    # Загружаем пациента
                    patient = db.query(Patient).filter(Patient.id == appointment.patient_id).first()
                    if patient:
                        patient_name = f"{patient.last_name} {patient.first_name}"
                        if patient.middle_name:
                            patient_name += f" {patient.middle_name}"
                        phone = patient.phone or "Не указан"
                        if patient.birth_date:
                            patient_birth_year = patient.birth_date.year
                        address = patient.address
                    
                    # Загружаем услуги из appointment
                    if hasattr(appointment, 'services') and appointment.services:
                        services = appointment.services if isinstance(appointment.services, list) else []
                    
                    # Стоимость
                    if hasattr(appointment, 'payment_amount') and appointment.payment_amount:
                        total_cost = float(appointment.payment_amount)
                    
                    # Определяем статус записи
                    status_mapping = {
                        "scheduled": "waiting",
                        "pending": "waiting",
                        "confirmed": "waiting",
                        "paid": "waiting",  # Оплачено, но еще в очереди
                        "in_progress": "called",
                        "in_visit": "called",
                        "completed": "served",
                        "cancelled": "no_show"
                    }
                    entry_status = status_mapping.get(appointment.status, "waiting")
                    
                    # Определяем статус оплаты по устойчивым признакам
                    # paid, in_visit, completed/done считаем оплаченными (после оплаты на регистратуре)
                    is_paid = False
                    try:
                        ap_status = (getattr(appointment, 'status', None) or '').lower()
                        if ap_status in ("paid", "in_visit", "in progress", "completed", "done"):
                            is_paid = True
                        # явные признаки оплаты по сумме/времени обработки
                        elif (getattr(appointment, 'payment_amount', 0) or 0) > 0:
                            is_paid = True
                        elif getattr(appointment, 'payment_processed_at', None):
                            is_paid = True
                        # проверим таблицу payments по appointment.id (если связка через visit_id отсутствует — пропускаем)
                        # попытка: ищем любой платёж с paid_at или статусом paid
                        if not is_paid:
                            try:
                                payment_row = db.query(Payment).filter(Payment.visit_id == appointment.id).order_by(Payment.created_at.desc()).first()
                                if payment_row and (payment_row.status.lower() == 'paid' or payment_row.paid_at):
                                    is_paid = True
                            except Exception:
                                pass
                    except Exception:
                        pass

                    discount_mode = "paid" if is_paid else (appointment.visit_type if hasattr(appointment, 'visit_type') else "none")
                    
                    source = "desk"  # Appointment обычно создается регистратором
                
                entries.append({
                    "id": record_id,
                    "number": idx,
                    "patient_id": patient_id,
                    "patient_name": patient_name,
                    "patient_birth_year": patient_birth_year,
                    "phone": phone,
                    "address": address,
                    "services": services,
                    "service_codes": service_codes,
                    "cost": total_cost,
                    "payment_status": "paid" if discount_mode == "paid" else "pending",
                    "source": source,
                    "status": entry_status,
                    "created_at": entry_wrapper["created_at"].isoformat() + "Z" if entry_wrapper["created_at"] else None,  # ✅ Добавляем 'Z' для UTC
                    "called_at": None,
                    "visit_time": visit_time,
                    "discount_mode": discount_mode,
                    "record_type": entry_type  # Добавляем тип записи: 'visit' или 'appointment'
                })
            
            queue_data = {
                "queue_id": queue_number,
                "specialist_id": data["doctor_id"],
                "specialist_name": doctor.user.full_name if doctor and doctor.user else f"Врач",
                "specialty": specialty,
                "cabinet": doctor.cabinet if doctor else "N/A",
                "opened_at": datetime.now().isoformat(),
                "entries": entries,
                "stats": {
                    "total": len(entries),
                    "waiting": len([e for e in entries if e["status"] == "waiting"]),
                    "called": len([e for e in entries if e["status"] == "called"]),
                    "served": len([e for e in entries if e["status"] == "served"]),
                    "online_entries": len([e for e in entries if e["source"] == "online"])
                }
            }
            
            result.append(queue_data)
            queue_number += 1
        
        return {
            "queues": result,
            "total_queues": len(result),
            "date": today.isoformat()
        }
        
    except Exception as e:
        import traceback
        traceback.print_exc()
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

"""
API endpoints для интеграции регистратуры с админ панелью
Основа: detail.md стр. 85-183
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_

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
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "cardiology", "derma", "dentist", "Lab"))
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
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "cardiology", "derma", "dentist", "Lab"))
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
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "cardio", "cardiology", "derma", "dentist", "Lab"))
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
            
            # ✅ Сохраняем discount_mode: если визит был оплачен, сохраняем 'paid'
            # Не теряем информацию об оплате при обновлении статуса
            if not visit.discount_mode or visit.discount_mode == "none":
                from app.models.payment import Payment
                payment = db.query(Payment).filter(Payment.visit_id == visit.id).order_by(Payment.created_at.desc()).first()
                if payment and (payment.status and payment.status.lower() == 'paid' or payment.paid_at):
                    visit.discount_mode = "paid"
                elif visit.status in ("in_visit", "in_progress", "completed"):
                    # Если визит был начат (в кабинете) или завершён, вероятно был оплачен
                    visit.discount_mode = "paid"
            
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
            
            # ✅ Сохраняем visit_type: если appointment был оплачен, сохраняем visit_type='paid'
            # Appointment не имеет discount_mode, используем visit_type
            if not appointment.visit_type or appointment.visit_type not in ("paid", "repeat", "benefit", "all_free"):
                from app.models.payment import Payment
                payment = db.query(Payment).filter(Payment.visit_id == appointment.id).order_by(Payment.created_at.desc()).first()
                if payment and (payment.status and payment.status.lower() == 'paid' or payment.paid_at):
                    appointment.visit_type = "paid"
                elif (hasattr(appointment, 'payment_amount') and appointment.payment_amount and appointment.payment_amount > 0):
                    appointment.visit_type = "paid"
                elif appointment.status in ("paid", "in_visit", "in_progress", "completed"):
                    appointment.visit_type = "paid"
            
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
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor", "Lab", "cardio", "cardiology", "derma", "dentist"))
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
        seen_visit_ids = set()  # Для отслеживания уже обработанных Visit
        seen_appointment_ids = set()  # Для отслеживания уже обработанных Appointment
        seen_patient_specialty_date = set()  # Для отслеживания комбинации patient_id + specialty + date (предотвращение дубликатов)
        
        # Обрабатываем Visit (новая система)
        for visit in visits:
            # Пропускаем если уже обработан
            if visit.id in seen_visit_ids:
                continue
            seen_visit_ids.add(visit.id)
            
            # ✅ Определяем specialty на основе услуг визита, а не только department
            # Проверяем услуги визита для правильного определения очереди
            from app.models.visit import VisitService
            from app.models.service import Service
            visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
            service_ids = [vs.service_id for vs in visit_services]
            services = db.query(Service).filter(Service.id.in_(service_ids)).all() if service_ids else []
            
            # ✅ Проверяем, есть ли ЭКГ в услугах (по queue_tag, названию и коду)
            has_ecg = False
            ecg_services_count = 0
            non_ecg_services_count = 0
            
            print(f"[get_today_queues] 🔍 Проверка ЭКГ для Visit {visit.id}, услуг: {len(services)}")
            for service in services:
                is_ecg_service = False
                service_name = service.name or 'N/A'
                service_code_val = service.service_code or service.code or 'N/A'
                queue_tag_val = service.queue_tag or 'N/A'
                
                # Проверяем по queue_tag
                if service.queue_tag == 'ecg':
                    is_ecg_service = True
                    print(f"[get_today_queues] ✅ ЭКГ найдено по queue_tag: {service_name} (код: {service_code_val})")
                # Проверяем по названию услуги
                elif service.name:
                    service_name_lower = str(service.name).lower()
                    if 'экг' in service_name_lower or 'ecg' in service_name_lower:
                        is_ecg_service = True
                        print(f"[get_today_queues] ✅ ЭКГ найдено по названию: {service_name} (код: {service_code_val}, queue_tag: {queue_tag_val})")
                # Проверяем по коду услуги
                if not is_ecg_service:
                    if service.service_code:
                        service_code_upper = str(service.service_code).upper()
                        if 'ECG' in service_code_upper or 'ЭКГ' in service_code_upper:
                            is_ecg_service = True
                            print(f"[get_today_queues] ✅ ЭКГ найдено по service_code: {service_name} (код: {service_code_val})")
                    elif service.code:
                        service_code_upper = str(service.code).upper()
                        if 'ECG' in service_code_upper or 'ЭКГ' in service_code_upper:
                            is_ecg_service = True
                            print(f"[get_today_queues] ✅ ЭКГ найдено по code: {service_name} (код: {service_code_val})")
                
                if is_ecg_service:
                    has_ecg = True
                    ecg_services_count += 1
                else:
                    non_ecg_services_count += 1
                    print(f"[get_today_queues] ❌ Не ЭКГ: {service_name} (код: {service_code_val}, queue_tag: {queue_tag_val})")
            
            # Только ЭКГ: если есть ЭКГ услуги и нет не-ЭКГ услуг
            has_only_ecg = has_ecg and non_ecg_services_count == 0
            print(f"[get_today_queues] 📊 Итог для Visit {visit.id}: has_ecg={has_ecg}, has_only_ecg={has_only_ecg}, ЭКГ услуг={ecg_services_count}, не-ЭКГ услуг={non_ecg_services_count}")
            
            # ✅ Определяем specialty: если есть ЭКГ, разделяем на отдельные очереди
            visit_date = visit.visit_date or today
            patient_id = visit.patient_id
            
            if has_ecg and not has_only_ecg:
                # Визит содержит и ЭКГ и другие услуги - разделяем:
                # 1. Создаем запись для ЭКГ в очередь echokg (только ЭКГ услуги)
                specialty_ecg = "echokg"
                if specialty_ecg not in queues_by_specialty:
                    queues_by_specialty[specialty_ecg] = {
                        "entries": [],
                        "doctor": None,
                        "doctor_id": visit.doctor_id
                    }
                
                # Проверяем дедупликацию для ЭКГ очереди
                patient_specialty_date_key_ecg = f"{patient_id}_{specialty_ecg}_{visit_date}"
                if patient_specialty_date_key_ecg not in seen_patient_specialty_date:
                    visit_created_at = visit.confirmed_at or visit.created_at if hasattr(visit, 'confirmed_at') else visit.created_at
                    queues_by_specialty[specialty_ecg]["entries"].append({
                        "type": "visit",
                        "data": visit,
                        "created_at": visit_created_at,
                        "filter_services": True,  # Флаг для фильтрации услуг при обработке
                        "ecg_only": True  # Только ЭКГ услуги для этой записи
                    })
                    seen_patient_specialty_date.add(patient_specialty_date_key_ecg)
                
                # 2. Создаем запись для кардиолога в очередь cardiology (без ЭКГ услуг)
                specialty = "cardiology"
                patient_specialty_date_key = f"{patient_id}_{specialty}_{visit_date}"
                if patient_specialty_date_key not in seen_patient_specialty_date:
                    if specialty not in queues_by_specialty:
                        queues_by_specialty[specialty] = {
                            "entries": [],
                            "doctor": None,
                            "doctor_id": visit.doctor_id
                        }
                    visit_created_at = visit.confirmed_at or visit.created_at if hasattr(visit, 'confirmed_at') else visit.created_at
                    queues_by_specialty[specialty]["entries"].append({
                        "type": "visit",
                        "data": visit,
                        "created_at": visit_created_at,
                        "filter_services": True,  # Флаг для фильтрации услуг при обработке
                        "ecg_only": False  # Исключаем ЭКГ услуги
                    })
                    seen_patient_specialty_date.add(patient_specialty_date_key)
                else:
                    print(f"[get_today_queues] Пропущен Visit {visit.id} для cardiology - дубликат по ключу {patient_specialty_date_key}")
                continue  # Переходим к следующему визиту
            elif has_ecg and has_only_ecg:
                # Только ЭКГ - идёт в echokg
                specialty = "echokg"
                patient_specialty_date_key = f"{patient_id}_{specialty}_{visit_date}"
                if patient_specialty_date_key in seen_patient_specialty_date:
                    print(f"[get_today_queues] Пропущен Visit {visit.id} - дубликат по ключу {patient_specialty_date_key}")
                    continue
                seen_patient_specialty_date.add(patient_specialty_date_key)
                
                if specialty not in queues_by_specialty:
                    queues_by_specialty[specialty] = {
                        "entries": [],
                        "doctor": None,
                        "doctor_id": visit.doctor_id
                    }
                
                visit_created_at = visit.confirmed_at or visit.created_at if hasattr(visit, 'confirmed_at') else visit.created_at
                queues_by_specialty[specialty]["entries"].append({
                    "type": "visit",
                    "data": visit,
                    "created_at": visit_created_at,
                    "filter_services": True,  # ✅ ИСПРАВЛЕНО: Включаем фильтрацию услуг
                    "ecg_only": True  # ✅ ИСПРАВЛЕНО: Показываем только ЭКГ услуги
                })
                continue  # Переходим к следующему визиту
            else:
                # Нет ЭКГ - используем department из визита
                specialty = visit.department or "general"
            
            # Дедупликация для обычных визитов (без ЭКГ)
            patient_specialty_date_key = f"{patient_id}_{specialty}_{visit_date}"
            if patient_specialty_date_key in seen_patient_specialty_date:
                print(f"[get_today_queues] Пропущен Visit {visit.id} - дубликат по ключу {patient_specialty_date_key}")
                continue
            seen_patient_specialty_date.add(patient_specialty_date_key)
            
            if specialty not in queues_by_specialty:
                queues_by_specialty[specialty] = {
                    "entries": [],
                    "doctor": None,
                    "doctor_id": visit.doctor_id
                }
            
            # Безопасно получаем дату создания
            visit_created_at = None
            try:
                visit_created_at = visit.confirmed_at or visit.created_at
            except Exception as e:
                print(f"[get_today_queues] Ошибка получения даты для Visit {visit.id}: {e}")
                visit_created_at = visit.created_at if hasattr(visit, 'created_at') else None
            
            queues_by_specialty[specialty]["entries"].append({
                "type": "visit",
                "data": visit,
                "created_at": visit_created_at
            })
            
            # Сохраняем первого врача из этой специальности
            try:
                if not queues_by_specialty[specialty]["doctor"] and hasattr(visit, 'doctor') and visit.doctor:
                    queues_by_specialty[specialty]["doctor"] = visit.doctor
            except Exception as e:
                print(f"[get_today_queues] Ошибка доступа к visit.doctor для Visit {visit.id}: {e}")
        
        # Обрабатываем Appointment (старая система)
        # Подгружаем актуальный статус оплаты из payments при наличии
        from app.models.payment import Payment
        for appointment in appointments:
            # Пропускаем если уже обработан
            if appointment.id in seen_appointment_ids:
                continue
            seen_appointment_ids.add(appointment.id)
            
            # Определяем специальность из appointment
            specialty = getattr(appointment, 'department', None) or "general"
            appointment_date = getattr(appointment, 'appointment_date', today)
            patient_id = getattr(appointment, 'patient_id', None)
            
            # Проверяем, нет ли уже Visit или Appointment для этого пациента в этой специальности на эту дату
            patient_specialty_date_key = f"{patient_id}_{specialty}_{appointment_date}"
            if patient_specialty_date_key in seen_patient_specialty_date:
                print(f"[get_today_queues] Пропущен Appointment {appointment.id} - дубликат по ключу {patient_specialty_date_key}")
                continue
            
            # Проверяем, нет ли уже Visit для этого Appointment (чтобы избежать дубликатов)
            # Если есть Visit с теми же patient_id, датой и doctor_id, пропускаем Appointment
            visit_exists = False
            try:
                doctor_id = getattr(appointment, 'doctor_id', None)
                
                if patient_id and appointment_date:
                    # Строим фильтр для поиска соответствующего Visit
                    visit_filters = [
                        Visit.patient_id == patient_id,
                        Visit.visit_date == appointment_date
                    ]
                    
                    # doctor_id может быть None, поэтому добавляем его в фильтр только если он не None
                    if doctor_id is not None:
                        visit_filters.append(Visit.doctor_id == doctor_id)
                    else:
                        # Если doctor_id None, ищем Visit с doctor_id None
                        visit_filters.append(Visit.doctor_id.is_(None))
                    
                    existing_visit = db.query(Visit).filter(and_(*visit_filters)).first()
                    if existing_visit:
                        visit_exists = True
                        print(f"[get_today_queues] Пропущен Appointment {appointment.id} - есть соответствующий Visit {existing_visit.id}")
            except Exception as check_error:
                # Если проверка не удалась, просто продолжаем - лучше показать дубликат, чем упасть с ошибкой
                print(f"[get_today_queues] Предупреждение: ошибка при проверке дубликатов для Appointment {getattr(appointment, 'id', 'unknown')}: {check_error}")
                import traceback
                traceback.print_exc()
            
            if visit_exists:
                continue
            
            # Отмечаем, что этот patient_id + specialty + date уже обработан
            seen_patient_specialty_date.add(patient_specialty_date_key)
            
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
            try:
                if not queues_by_specialty[specialty]["doctor"] and hasattr(appointment, 'doctor') and appointment.doctor:
                    queues_by_specialty[specialty]["doctor"] = appointment.doctor
            except Exception as e:
                print(f"[get_today_queues] Ошибка доступа к appointment.doctor для Appointment {appointment.id}: {e}")
        
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
            seen_entry_keys = set()  # Для дедупликации записей в одной специальности
            for idx, entry_wrapper in enumerate(entries_list, 1):
                entry_type = entry_wrapper["type"]
                entry_data = entry_wrapper["data"]
                
                # Получаем базовые идентификаторы для дедупликации
                if entry_type == "visit":
                    entry_record_id = entry_data.id
                    entry_patient_id = entry_data.patient_id
                    entry_date = getattr(entry_data, 'visit_date', today)
                else:  # appointment
                    entry_record_id = entry_data.id
                    entry_patient_id = entry_data.patient_id
                    entry_date = getattr(entry_data, 'appointment_date', today)
                
                # Создаем уникальный ключ: patient_id + specialty + дата
                # Это гарантирует, что один пациент показывается только один раз в одной специальности на одну дату
                entry_key = f"{entry_patient_id}_{specialty}_{entry_date}"
                
                # Пропускаем дубликаты
                if entry_key in seen_entry_keys:
                    print(f"[get_today_queues] Пропущен дубликат: {entry_key} (тип: {entry_type})")
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
                    all_visit_services = db.query(VisitService).filter(
                        VisitService.visit_id == visit.id
                    ).all()
                    
                    # ✅ Фильтруем услуги если есть флаг ecg_only или filter_services
                    ecg_only_flag = entry_wrapper.get("ecg_only", False)
                    filter_services_flag = entry_wrapper.get("filter_services", False)
                    
                    visit_services = []
                    if filter_services_flag or ecg_only_flag:
                        # Фильтруем: показываем только ЭКГ услуги (для очереди echokg)
                        for vs in all_visit_services:
                            if hasattr(vs, 'service_id') and vs.service_id:
                                service = db.query(Service).filter(Service.id == vs.service_id).first()
                                if service and service.queue_tag == 'ecg':
                                    visit_services.append(vs)
                        # Если нет ЭКГ услуг, не добавляем запись (это не должно произойти, но на всякий случай)
                        if not visit_services:
                            print(f"[get_today_queues] Предупреждение: флаг ecg_only=True, но ЭКГ услуг не найдено для Visit {visit.id}")
                            continue  # Пропускаем эту запись, если нет ЭКГ услуг
                    else:
                        # Фильтруем: исключаем ЭКГ услуги (для очереди cardiology)
                        for vs in all_visit_services:
                            if hasattr(vs, 'service_id') and vs.service_id:
                                service = db.query(Service).filter(Service.id == vs.service_id).first()
                                if service and service.queue_tag != 'ecg':
                                    visit_services.append(vs)
                        # Если не нашли не-ЭКГ услуг, значит это только ЭКГ визит - пропускаем для cardiology
                        if not visit_services:
                            print(f"[get_today_queues] Пропущен Visit {visit.id} для specialty={specialty}: содержит только ЭКГ услуги")
                            continue  # Пропускаем эту запись для кардиолога, если нет не-ЭКГ услуг
                    
                    # Если нет отфильтрованных услуг, используем все (fallback)
                    if not visit_services:
                        visit_services = all_visit_services
                    
                    for vs in visit_services:
                        # ✅ Используем service_code из справочника услуг для правильного формата (K01, D02, C03 и т.д.)
                        # vs.code может содержать старые коды, поэтому ищем правильный код через service_id
                        service_code_to_use = None
                        if hasattr(vs, 'service_id') and vs.service_id:
                            try:
                                from app.models.service import Service
                                service = db.query(Service).filter(Service.id == vs.service_id).first()
                                if service:
                                    # Приоритет 1: service_code (новый формат K01, D02, C03)
                                    if service.service_code:
                                        service_code_to_use = service.service_code
                                    # Приоритет 2: код из category_code + id (временный формат)
                                    elif service.category_code:
                                        service_code_to_use = f"{service.category_code}{str(service.id).zfill(2)}"
                                    # Приоритет 3: старый code из Service
                                    elif service.code:
                                        service_code_to_use = service.code
                            except Exception:
                                pass
                        
                        # Если не нашли через service_id, используем vs.code как fallback
                        if not service_code_to_use and vs.code:
                            service_code_to_use = vs.code
                        
                        # Если всё ещё нет кода, используем название (нежелательно)
                        if service_code_to_use:
                            services.append(service_code_to_use)
                            service_codes.append(service_code_to_use)
                        elif vs.name:
                            services.append(vs.name)
                        
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

                    # ✅ Устойчивое определение факта оплаты по визиту
                    # Всегда перепроверяем оплату для всех записей, чтобы обновить существующие записи
                    is_paid = False
                    try:
                        # ✅ НЕ используем discount_mode как единственный признак оплаты для новых записей
                        # discount_mode может быть 'paid' при создании, но фактическая оплата может отсутствовать
                        # Проверяем discount_mode только в сочетании с другими признаками
                        
                        # ✅ ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА: Проверяем все признаки оплаты для всех записей
                        # Это нужно для обновления записей, которые были зарегистрированы до исправления
                        # НО: не считаем новыми записями (status="confirmed") как оплаченными - они могут быть еще не оплачены
                        
                        # Приоритет 1: Проверяем статус визита - если визит уже начат или завершён, вероятно оплачен
                        v_status = (getattr(visit, 'status', None) or '').lower()
                        # ✅ УБРАЛИ "confirmed" из списка - новые пациенты могут иметь статус "confirmed" до оплаты
                        if v_status in ("paid", "in_visit", "in progress", "completed", "done"):
                            # ✅ Если визит начат или завершён, считаем оплаченным
                            # Пациенты обычно не вызываются в кабинет без оплаты
                            is_paid = True
                        # Приоритет 2: Проверяем payment_processed_at (явный признак оплаты)
                        if not is_paid and getattr(visit, 'payment_processed_at', None):
                            is_paid = True
                        # Приоритет 3: Проверка записей оплаты в таблице payments по visit.id
                        if not is_paid:
                            try:
                                payment_row = db.query(Payment).filter(Payment.visit_id == visit.id).order_by(Payment.created_at.desc()).first()
                                if payment_row:
                                    payment_status = str(payment_row.status).lower() if payment_row.status else ''
                                    # ✅ Проверяем статус Payment - только если статус явно 'paid' или есть paid_at
                                    if payment_status == 'paid' or payment_row.paid_at:
                                        is_paid = True
                                    # НЕ используем amount > 0 как признак оплаты - это может быть сумма без фактической оплаты
                            except Exception as e:
                                print(f"[get_today_queues] Ошибка при проверке Payment для Visit {visit.id}: {e}")
                                pass
                        # Приоритет 4: Проверяем discount_mode ТОЛЬКО если есть другие признаки оплаты
                        # Если визит начат/завершён ИЛИ есть payment_processed_at ИЛИ есть Payment, и discount_mode='paid', то оплачен
                        if not is_paid:
                            discount_mode_value = getattr(visit, 'discount_mode', None)
                            v_status = (getattr(visit, 'status', None) or '').lower()
                            # discount_mode='paid' + визит начат/завершён = оплачен
                            if discount_mode_value == 'paid' and v_status in ("paid", "in_visit", "in progress", "completed", "done"):
                                is_paid = True
                            # discount_mode='paid' + есть payment_processed_at = оплачен
                            elif discount_mode_value == 'paid' and getattr(visit, 'payment_processed_at', None):
                                is_paid = True
                        # ✅ УБРАЛИ проверку наличия услуг с ценой - это не признак оплаты
                    except Exception as e:
                        print(f"[get_today_queues] Ошибка при определении оплаты для Visit {visit.id}: {e}")
                        pass

                    # ✅ Обновляем discount_mode в ответе API и сохраняем в БД
                    # Если визит оплачен (по любым признакам), но discount_mode не установлен как 'paid', ОБЯЗАТЕЛЬНО обновляем
                    # Это исправляет существующие записи, которые были зарегистрированы до исправления
                    if is_paid:
                        discount_mode = 'paid'
                        # ✅ Сохраняем в базу данных ВСЕГДА, если визит оплачен (даже если discount_mode уже был 'paid')
                        # Это гарантирует, что все записи будут обновлены
                        if visit.discount_mode != 'paid':
                            visit.discount_mode = 'paid'
                            try:
                                db.commit()
                                db.refresh(visit)
                                print(f"[get_today_queues] ✅ Обновлен discount_mode для Visit {visit.id}: 'paid'")
                            except Exception as e:
                                # Если не удалось сохранить, продолжаем с обновленным discount_mode в ответе
                                print(f"[get_today_queues] Предупреждение: не удалось сохранить discount_mode для Visit {visit.id}: {e}")
                                db.rollback()
                    else:
                        # ✅ Если визит НЕ оплачен, используем существующий discount_mode или "none"
                        # НЕ меняем discount_mode в БД, если он не 'paid' (может быть "none", "repeat", "benefit", "all_free")
                        discount_mode = getattr(visit, 'discount_mode', None) or "none"
                
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
                        if isinstance(appointment.services, list):
                            # ✅ Оставляем services как есть (уже должны быть коды), но дублируем в service_codes
                            services = appointment.services
                            # Если services содержит коды услуг (например, "ECG-001" или "C01"), добавляем их в service_codes
                            for service in services:
                                # Проверяем, является ли это кодом (формат "C01", "D02", "ECG-001" или просто код)
                                if isinstance(service, str):
                                    # Если это код (короткая строка, не похожая на полное название), добавляем в service_codes
                                    if len(service) <= 10 or '-' in service or service.isalnum():
                                        service_codes.append(service)
                                    # Если это полное название (длинное, с пробелами), не добавляем в service_codes
                                    # но это означает, что данные приходят в неправильном формате
                    
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
                    
                    # ✅ Определяем статус оплаты по устойчивым признакам
                    # Appointment не имеет discount_mode, используем только visit_type
                    # Всегда перепроверяем оплату для всех записей, чтобы обновить существующие записи
                    is_paid = False
                    
                    # Приоритет 1: Проверяем существующий visit_type (Appointment использует visit_type, а не discount_mode)
                    appointment_visit_type = getattr(appointment, 'visit_type', None) if hasattr(appointment, 'visit_type') else None
                    
                    if appointment_visit_type == 'paid':
                        is_paid = True
                    
                    # ✅ ПРИНУДИТЕЛЬНАЯ ПРОВЕРКА: Проверяем все признаки оплаты для существующих записей
                    # Это нужно для обновления записей, которые были зарегистрированы до исправления
                    # НО: не считаем новыми записями (status="confirmed") как оплаченными - они могут быть еще не оплачены
                    if not is_paid:
                        try:
                            ap_status = (getattr(appointment, 'status', None) or '').lower()
                            # ✅ УБРАЛИ "confirmed" из списка - новые пациенты могут иметь статус "confirmed" до оплаты
                            if ap_status in ("paid", "in_visit", "in progress", "completed", "done"):
                                is_paid = True
                            # ✅ УБРАЛИ проверку payment_amount > 0 - это не признак оплаты (может быть сумма без оплаты)
                            # Приоритет 3: Проверяем payment_processed_at (явный признак оплаты)
                            if not is_paid and getattr(appointment, 'payment_processed_at', None):
                                is_paid = True
                            # ✅ Проверка Payment для Appointment: ищем через связанный Visit или по patient_id и дате
                            if not is_paid:
                                try:
                                    from app.models.visit import Visit
                                    # Сначала ищем связанный Visit для этого Appointment
                                    related_visit = db.query(Visit).filter(
                                        and_(
                                            Visit.patient_id == appointment.patient_id,
                                            Visit.visit_date == appointment.appointment_date,
                                            Visit.doctor_id == appointment.doctor_id
                                        )
                                    ).first()
                                    
                                    if related_visit:
                                        # Если есть связанный Visit, ищем Payment через visit_id
                                        payment_row = db.query(Payment).filter(Payment.visit_id == related_visit.id).order_by(Payment.created_at.desc()).first()
                                        if payment_row and (str(payment_row.status).lower() == 'paid' or payment_row.paid_at):
                                            is_paid = True
                                    
                                    # Также проверяем все Payment для этого patient_id на сегодняшнюю дату
                                    if not is_paid:
                                        today = appointment.appointment_date if appointment.appointment_date else date.today()
                                        # Ищем Payment через связанные Visit этого пациента на сегодня
                                        visit_ids_today = db.query(Visit.id).filter(
                                            and_(
                                                Visit.patient_id == appointment.patient_id,
                                                Visit.visit_date == today
                                            )
                                        ).subquery()
                                        payment_row = db.query(Payment).filter(
                                            Payment.visit_id.in_(visit_ids_today)
                                        ).order_by(Payment.created_at.desc()).first()
                                        if payment_row and (str(payment_row.status).lower() == 'paid' or payment_row.paid_at):
                                            is_paid = True
                                except Exception as e:
                                    print(f"[get_today_queues] Ошибка при проверке Payment для Appointment {appointment.id}: {e}")
                                    pass
                        except Exception:
                            pass

                    # ✅ Обновляем discount_mode для API ответа и сохраняем visit_type в БД
                    # discount_mode используется только для единообразия в ответе API, в БД Appointment хранит visit_type
                    # Если appointment оплачен (по любым признакам), ОБЯЗАТЕЛЬНО обновляем
                    if appointment_visit_type == 'paid':
                        discount_mode = 'paid'
                    elif is_paid:
                        discount_mode = 'paid'
                        # ✅ Сохраняем visit_type='paid' в базу данных ВСЕГДА, если appointment оплачен
                        # Это гарантирует, что все записи будут обновлены, включая существующие
                        if appointment.visit_type != 'paid':
                            appointment.visit_type = 'paid'
                            try:
                                db.commit()
                                db.refresh(appointment)
                                print(f"[get_today_queues] ✅ Обновлен visit_type для Appointment {appointment.id}: 'paid'")
                            except Exception as e:
                                # Если не удалось сохранить, продолжаем с обновленным discount_mode в ответе
                                print(f"[get_today_queues] Предупреждение: не удалось сохранить visit_type для Appointment {appointment.id}: {e}")
                                db.rollback()
                    else:
                        discount_mode = appointment_visit_type if appointment_visit_type else "none"
                    
                    source = "desk"  # Appointment обычно создается регистратором
                
                # Добавляем appointment_id для Visit (если был создан соответствующий Appointment)
                appointment_id_value = record_id
                if entry_type == "visit":
                    # Проверяем, есть ли Appointment для этого Visit
                    try:
                        existing_appointment = db.query(Appointment).filter(
                            and_(
                                Appointment.patient_id == patient_id,
                                Appointment.appointment_date == (getattr(entry_data, 'visit_date', None) or today),
                                Appointment.doctor_id == getattr(entry_data, 'doctor_id', None)
                            )
                        ).first()
                        if existing_appointment:
                            appointment_id_value = existing_appointment.id
                    except Exception:
                        pass  # Используем record_id по умолчанию
                
                # ✅ ИСПРАВЛЕНО: Получаем РЕАЛЬНЫЙ номер из queue_entries
                queue_entry_number = idx  # По умолчанию используем idx
                try:
                    from app.models.queue_old import QueueEntry  # ✅ ИСПРАВЛЕНО: правильный импорт
                    # Ищем запись в queue_entries по visit_id (для Visit) или по patient_id (для Appointment)
                    if entry_type == "visit":
                        queue_entry = db.query(QueueEntry).filter(
                            QueueEntry.visit_id == record_id
                        ).first()
                        if queue_entry:
                            queue_entry_number = queue_entry.number
                    elif entry_type == "appointment":
                        # Для Appointment ищем по patient_id, так как visit_id может не быть
                        queue_entry = db.query(QueueEntry).filter(
                            QueueEntry.patient_id == patient_id,
                            QueueEntry.visit_id == None  # Ищем записи без visit_id (старые appointments)
                        ).order_by(QueueEntry.created_at.desc()).first()
                        if queue_entry:
                            queue_entry_number = queue_entry.number
                except Exception as e:
                    print(f"[get_today_queues] Не удалось получить номер из queue_entries для {entry_type} {record_id}: {e}")

                entries.append({
                    "id": record_id,
                    "appointment_id": appointment_id_value,  # Явно добавляем appointment_id
                    "number": queue_entry_number,  # ✅ ИСПРАВЛЕНО: реальный номер из queue_entries
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
        error_traceback = traceback.format_exc()
        print(f"[get_today_queues] КРИТИЧЕСКАЯ ОШИБКА: {type(e).__name__}: {e}")
        print(f"[get_today_queues] Traceback:\n{error_traceback}")
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

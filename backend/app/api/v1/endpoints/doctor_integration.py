"""
API endpoints для интеграции панелей врачей с системой
Основа: passport.md стр. 1141-2063
"""
import logging
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Any
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from sqlalchemy import and_
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.visit import Visit, VisitService
from app.models.service import Service
from app.crud import clinic as crud_clinic
from app.crud import online_queue as crud_queue
from app.crud import visit as crud_visit
from app.services.notification_service import NotificationService
from app.services.service_mapping import get_service_code

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================

class ScheduleNextVisitService(BaseModel):
    service_id: int
    quantity: int = 1
    custom_price: Optional[float] = None

class ScheduleNextVisitRequest(BaseModel):
    patient_id: int
    services: List[ScheduleNextVisitService]
    visit_date: date
    visit_time: Optional[str] = None
    discount_mode: str = Field(default="none", pattern="^(none|repeat|benefit|all_free)$")
    all_free: bool = False
    notes: Optional[str] = None
    confirmation_channel: str = Field(default="phone", pattern="^(phone|telegram|pwa|auto)$")

class ScheduleNextVisitResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str  # pending_confirmation
    confirmation: Dict[str, Any]

# ===================== ОЧЕРЕДЬ ВРАЧА =====================

@router.get("/doctor/{specialty}/queue/today")
def get_doctor_queue_today(
    specialty: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist", "Lab"))
):
    """
    Получить очередь врача на сегодня
    Из passport.md стр. 1419: GET /api/doctor/cardiology/queue/today
    """
    try:
        # Нормализуем название специальности для поиска
        specialty_mapping = {
            'cardiology': ['cardiology', 'cardio', 'Cardiologist', 'Cardio'],
            'cardio': ['cardiology', 'cardio', 'Cardiologist', 'Cardio'],
            'derma': ['derma', 'dermatology', 'Dermatologist'],
            'dentist': ['dentist', 'dental', 'dentistry', 'Dentist'],
            'lab': ['lab', 'laboratory', 'Laboratory']
        }
        
        # Получаем возможные варианты специальности
        specialty_variants = specialty_mapping.get(specialty.lower(), [specialty])
        
        # Получаем врача по специальности и пользователю
        doctor = db.query(Doctor).filter(
            and_(
                Doctor.specialty.in_(specialty_variants),
                Doctor.user_id == current_user.id,
                Doctor.active == True
            )
        ).first()
        
        if not doctor:
            # Если врач не найден по user_id, ищем по специальности (для админа и других ролей)
            doctor = db.query(Doctor).filter(
                and_(
                    Doctor.specialty.in_(specialty_variants),
                    Doctor.active == True
                )
            ).first()
            
            if not doctor:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Врач специальности '{specialty}' не найден. Проверенные варианты: {specialty_variants}"
                )
        
        today = date.today()
        
        # ⭐ ВАЖНО: DailyQueue.specialist_id - это user_id, а не doctor_id
        # Получаем дневную очередь по user_id
        doctor_user_id = doctor.user_id if doctor.user_id else None
        daily_queue = None
        if doctor_user_id:
            daily_queue = db.query(DailyQueue).filter(
                and_(DailyQueue.day == today, DailyQueue.specialist_id == doctor_user_id)
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist", "Lab"))
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

        if not daily_queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Очередь не найдена"
            )

        doctor = daily_queue.specialist

        if not doctor:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден для этой очереди"
            )

        if current_user.role != "Admin" and doctor.user_id and doctor.user_id != current_user.id:
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
            logger.warning("Не удалось отправить на табло: %s", ws_error, exc_info=True)
        
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist", "Lab"))
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
        
        # Создаем или обновляем визит в таблице visits
        visit = crud_visit.find_or_create_today_visit(
            db=db,
            patient_id=queue_entry.patient_id,
            doctor_id=current_user.id,
            department=queue_entry.queue.department if hasattr(queue_entry, 'queue') else "general"
        )
        
        # Обновляем время начала приема
        visit.visit_time = datetime.now().strftime("%H:%M")
        visit.notes = f"Прием начат в {datetime.now().strftime('%H:%M')}"
        
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist", "Lab"))
):
    """
    Завершить прием пациента
    Из passport.md стр. 1425: POST /api/visits/:id/complete
    """
    try:
        from app.models.visit import Visit
        from app.models.appointment import Appointment
        
        # Сначала ищем в Visit
        visit = db.query(Visit).filter(Visit.id == entry_id).first()
        if visit:
            # Обновляем статус визита
            visit.status = "completed"
            
            # ✅ ИСПРАВЛЕНО: Сохраняем discount_mode и создаем платеж через SSOT
            # Проверяем через Payment или по существующему discount_mode
            from app.models.payment import Payment
            if not visit.discount_mode or visit.discount_mode == "none":
                payment = db.query(Payment).filter(Payment.visit_id == visit.id).order_by(Payment.created_at.desc()).first()
                if payment and (payment.status and payment.status.lower() == 'paid' or payment.paid_at):
                    visit.discount_mode = "paid"
                elif visit.status in ("in_visit", "in_progress", "completed"):
                    # ✅ ИСПРАВЛЕНО: Если визит был начат (в кабинете) или завершён, вероятно был оплачен
                    # Создаем платеж через SSOT
                    from app.services.billing_service import BillingService
                    billing_service = BillingService(db)
                    
                    # Проверяем, не создан ли уже платеж
                    if not payment:
                        # Рассчитываем сумму визита через SSOT
                        total_info = billing_service.calculate_total(
                            visit_id=visit.id,
                            discount_mode=visit.discount_mode or "none"
                        )
                        payment_amount = float(total_info["total"])
                        
                        # Создаем платеж через SSOT
                        payment = billing_service.create_payment(
                            visit_id=visit.id,
                            amount=payment_amount,
                            currency=total_info.get("currency", "UZS"),
                            method="cash",  # Предполагаем наличные для визитов в процессе
                            status="paid",
                            note=f"Автоматическое создание платежа при завершении приема (visit {visit.id})"
                        )
                        logger.info("complete_visit: Создан платеж ID=%d для визита %d, сумма=%s", payment.id, visit.id, payment_amount)
                    
                    visit.discount_mode = "paid"
            
            db.commit()
            db.refresh(visit)
            
            # Завершаем визит с медицинскими данными
            if visit_data:
                crud_visit.complete_visit(
                    db=db,
                    visit_id=visit.id,
                    medical_data=visit_data
                )
            
            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed"
            }
        
        # Если не найден в Visit, ищем в Appointment
        appointment = db.query(Appointment).filter(Appointment.id == entry_id).first()
        if appointment:
            # Обновляем статус appointment
            appointment.status = "completed"
            
            # ✅ Сохраняем информацию об оплате: если appointment был оплачен, сохраняем visit_type='paid'
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
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed"
            }
        
        # Если не найден ни в Visit, ни в Appointment — пробуем завершить по записи очереди
        from app.models.online_queue import OnlineQueueEntry
        queue_entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
        if queue_entry:
            # Проверяем права врача на эту очередь
            daily_queue = queue_entry.queue
            doctor = daily_queue.specialist if daily_queue else None
            if doctor and current_user.role != "Admin" and doctor.user_id != current_user.id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Нет прав для работы с этой очередью"
                )

            # Отмечаем запись очереди как обслуженную
            queue_entry.status = "served"
            db.commit()
            db.refresh(queue_entry)

            # Создаем или обновляем визит на сегодня и помечаем как завершенный,
            # чтобы это отразилось в registrar/queues/today, который читает Visit/Appointment
            try:
                visit = crud_visit.find_or_create_today_visit(
                    db=db,
                    patient_id=queue_entry.patient_id,
                    doctor_id=current_user.id,
                    department=daily_queue.department if daily_queue and hasattr(daily_queue, 'department') else "cardiology"
                )
                # ✅ Обновляем статус визита на completed
                visit.status = "completed"
                
                # ✅ ИСПРАВЛЕНО: Проверяем и сохраняем информацию об оплате, создаем платеж через SSOT
                # Если визит был оплачен (есть записи в Payment или статус указывает на оплату)
                from app.models.payment import Payment
                payment = db.query(Payment).filter(Payment.visit_id == visit.id).order_by(Payment.created_at.desc()).first()
                if payment and (payment.status and payment.status.lower() == 'paid' or payment.paid_at):
                    # Визит оплачен - устанавливаем discount_mode и payment_processed_at
                    visit.discount_mode = "paid"
                    if hasattr(visit, 'payment_processed_at') and not visit.payment_processed_at:
                        visit.payment_processed_at = payment.paid_at or datetime.utcnow()
                elif not visit.discount_mode or visit.discount_mode == "none":
                    # ✅ ИСПРАВЛЕНО: Если нет информации об оплате, но был вызван в кабинет - считаем что оплачен
                    # Создаем платеж через SSOT
                    from app.services.billing_service import BillingService
                    billing_service = BillingService(db)
                    
                    # Проверяем, не создан ли уже платеж
                    if not payment:
                        # Рассчитываем сумму визита через SSOT
                        total_info = billing_service.calculate_total(
                            visit_id=visit.id,
                            discount_mode=visit.discount_mode or "none"
                        )
                        payment_amount = float(total_info["total"])
                        
                        # Создаем платеж через SSOT
                        payment = billing_service.create_payment(
                            visit_id=visit.id,
                            amount=payment_amount,
                            currency=total_info.get("currency", "UZS"),
                            method="cash",  # Предполагаем наличные для визитов в процессе
                            status="paid",
                            note=f"Автоматическое создание платежа при завершении приема из очереди (visit {visit.id})"
                        )
                        logger.info("complete_queue_visit: Создан платеж ID=%d для визита %d, сумма=%s", payment.id, visit.id, payment_amount)
                    
                    visit.discount_mode = "paid"
                    if hasattr(visit, 'payment_processed_at') and not visit.payment_processed_at:
                        visit.payment_processed_at = payment.paid_at or datetime.utcnow() if payment else datetime.utcnow()
                
                # ✅ Также обновляем соответствующий Appointment, если он существует
                from app.models.appointment import Appointment
                appointment = db.query(Appointment).filter(
                    and_(
                        Appointment.patient_id == queue_entry.patient_id,
                        Appointment.appointment_date == visit.visit_date if visit.visit_date else date.today(),
                        Appointment.doctor_id == visit.doctor_id
                    )
                ).first()
                
                if appointment:
                    appointment.status = "completed"
                    # Сохраняем discount_mode для appointment
                    if not appointment.discount_mode or appointment.discount_mode == "none":
                        if visit.discount_mode == "paid":
                            appointment.discount_mode = "paid"
                        elif hasattr(appointment, 'payment_amount') and appointment.payment_amount and appointment.payment_amount > 0:
                            appointment.discount_mode = "paid"
                
                if visit_data:
                    # Сохраняем медицинские данные, если переданы
                    crud_visit.complete_visit(
                        db=db,
                        visit_id=visit.id,
                        medical_data=visit_data
                    )
                
                # ✅ Коммитим все изменения (Visit и Appointment)
                db.commit()
                db.refresh(visit)
                if appointment:
                    db.refresh(appointment)
            except Exception as e:
                # Не блокируем основной флоу очереди, если с визитом что-то пошло не так
                logger.warning(f"Ошибка создания/обновления визита при завершении приема: {e}")
                db.rollback()

            return {
                "success": True,
                "message": "Прием пациента завершен",
                "entry_id": entry_id,
                "status": "completed"
            }

        # Иначе действительно не найдено
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Запись не найдена")
        
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist", "Lab"))
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"))
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"))
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
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "cardio", "cardiology", "derma", "dentist"))
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
                DailyQueue.specialist_id == doctor.user_id,  # ⭐ user_id, а не doctor.id
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


# ===================== НАЗНАЧЕНИЕ СЛЕДУЮЩЕГО ВИЗИТА =====================

@router.post("/doctor/visits/schedule-next", response_model=ScheduleNextVisitResponse)
async def schedule_next_visit(
    request: ScheduleNextVisitRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist"))
):
    """
    Назначение следующего визита врачом (без номера в очереди)
    Номер будет присвоен только после подтверждения пациентом
    """
    try:
        # Получаем врача
        doctor = db.query(Doctor).filter(
            and_(Doctor.user_id == current_user.id, Doctor.active == True)
        ).first()
        
        if not doctor and current_user.role != "Admin":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Профиль врача не найден"
            )
        
        # Проверяем что дата не в прошлом
        if request.visit_date < date.today():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Нельзя назначить визит на прошедшую дату"
            )
        
        # Проверяем существование пациента
        from app.models.patient import Patient
        patient = db.query(Patient).filter(Patient.id == request.patient_id).first()
        if not patient:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Пациент не найден"
            )
        
        # Проверяем существование услуг
        service_ids = [s.service_id for s in request.services]
        services = db.query(Service).filter(Service.id.in_(service_ids)).all()
        
        if len(services) != len(service_ids):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Некоторые услуги не найдены"
            )
        
        # Генерируем токен подтверждения
        confirmation_token = str(uuid.uuid4())
        expires_at = datetime.utcnow() + timedelta(hours=48)  # 48 часов на подтверждение
        
        # Создаем визит со статусом pending_confirmation
        visit = Visit(
            patient_id=request.patient_id,
            doctor_id=doctor.id if doctor else None,
            visit_date=request.visit_date,
            visit_time=request.visit_time,
            status="pending_confirmation",  # Ожидает подтверждения
            discount_mode=request.discount_mode,
            department="mixed",  # Будет определен по услугам
            notes=request.notes,
            confirmation_token=confirmation_token,
            confirmation_channel=request.confirmation_channel,
            confirmation_expires_at=expires_at
        )
        db.add(visit)
        db.flush()  # Получаем ID визита
        
        # Добавляем услуги к визиту
        total_amount = 0
        for service_req in request.services:
            service = next(s for s in services if s.id == service_req.service_id)
            
            # Вычисляем цену
            service_price = service_req.custom_price or (float(service.price) if service.price else 0)
            
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
                code=get_service_code(service.id, db) or service.code,
                qty=service_req.quantity,
                price=service_price,
                currency="UZS"
            )
            db.add(visit_service)
            
            total_amount += service_price * service_req.quantity
        
        db.commit()
        db.refresh(visit)
        
        # Отправляем приглашение на подтверждение
        notification_service = NotificationService(db)
        try:
            notification_result = await notification_service.send_visit_confirmation_invitation(
                visit=visit,
                channel=request.confirmation_channel
            )
            logger.info(f"Приглашение отправлено для визита {visit.id}: {notification_result}")
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
            "notification_sent": notification_result.get("success", False) if 'notification_result' in locals() else False
        }
        
        return ScheduleNextVisitResponse(
            success=True,
            message=f"Визит назначен на {request.visit_date}. Ожидает подтверждения пациентом.",
            visit_id=visit.id,
            status="pending_confirmation",
            confirmation=confirmation_data
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка назначения следующего визита: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка назначения визита: {str(e)}"
        )


# ===================== УПРАВЛЕНИЕ ВИЗИТАМИ =====================

@router.get("/doctor/visits/today")
def get_today_visits(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist"))
):
    """Получить сегодняшние визиты врача"""
    try:
        visits = crud_visit.get_today_visits_by_doctor(db=db, doctor_id=current_user.id)
        
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
                    "service_name": service.name if service else f"Услуга #{vs.service_id}",
                    "quantity": vs.quantity,
                    "price": vs.price,
                    "custom_price": vs.custom_price,
                    "total": vs.price * vs.quantity
                }
                services_data.append(service_data)
                total_amount += service_data["total"]
            
            result.append({
                "id": visit.id,
                "patient_id": visit.patient_id,
                "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
                "visit_time": visit.visit_time,
                "status": visit.status,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "notes": visit.notes,
                "services": services_data,
                "total_amount": total_amount,
                "created_at": visit.created_at.isoformat() if visit.created_at else None
            })
        
        return {
            "success": True,
            "visits": result,
            "total_count": len(result)
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения визитов: {str(e)}"
        )


@router.get("/doctor/visits/{visit_id}")
def get_visit_details(
    visit_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar", "Cashier", "Receptionist", "cardio", "cardiology", "derma", "dentist"))
):
    """Получить детали визита"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)
        
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        # Проверяем права доступа
        if current_user.role not in ["Admin"] and visit.doctor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому визиту"
            )
        
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
                "service_code": service.code if service else None,
                "quantity": vs.quantity,
                "price": vs.price,
                "custom_price": vs.custom_price,
                "total": vs.price * vs.quantity
            }
            services_data.append(service_data)
            total_amount += service_data["total"]
        
        return {
            "success": True,
            "visit": {
                "id": visit.id,
                "patient_id": visit.patient_id,
                "doctor_id": visit.doctor_id,
                "visit_date": visit.visit_date.isoformat() if visit.visit_date else None,
                "visit_time": visit.visit_time,
                "status": visit.status,
                "department": visit.department,
                "discount_mode": visit.discount_mode,
                "approval_status": visit.approval_status,
                "notes": visit.notes,
                "services": services_data,
                "total_amount": total_amount,
                "created_at": visit.created_at.isoformat() if visit.created_at else None,
                "confirmed_at": visit.confirmed_at.isoformat() if visit.confirmed_at else None
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения визита: {str(e)}"
        )


@router.put("/doctor/visits/{visit_id}/add-service")
def add_service_to_visit(
    visit_id: int,
    service_id: int,
    quantity: int = 1,
    custom_price: Optional[float] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist"))
):
    """Добавить услугу к визиту"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)
        
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        # Проверяем права доступа
        if current_user.role not in ["Admin"] and visit.doctor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому визиту"
            )
        
        # Проверяем, что услуга существует
        service = db.query(Service).filter(Service.id == service_id).first()
        if not service:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Услуга не найдена"
            )
        
        # Добавляем услугу
        visit_service = crud_visit.add_visit_service(
            db=db,
            visit_id=visit_id,
            service_id=service_id,
            quantity=quantity,
            custom_price=custom_price
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
                "total": visit_service.price * visit_service.quantity
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка добавления услуги: {str(e)}"
        )


@router.delete("/doctor/visits/{visit_id}/services/{visit_service_id}")
def remove_service_from_visit(
    visit_id: int,
    visit_service_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist"))
):
    """Удалить услугу из визита"""
    try:
        visit = crud_visit.get_visit(db=db, visit_id=visit_id)
        
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        # Проверяем права доступа
        if current_user.role not in ["Admin"] and visit.doctor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет доступа к этому визиту"
            )
        
        # Удаляем услугу
        success = crud_visit.remove_visit_service(db=db, visit_service_id=visit_service_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Услуга в визите не найдена"
            )
        
        return {
            "success": True,
            "message": "Услуга удалена из визита"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка удаления услуги: {str(e)}"
        )


@router.get("/doctor/visits/statistics")
def get_visit_statistics(
    date_from: Optional[str] = Query(None, description="Дата начала в формате YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Дата окончания в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "cardio", "cardiology", "derma", "dentist"))
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
            doctor_id=current_user.id,
            date_from=date_from_obj,
            date_to=date_to_obj
        )
        
        return {
            "success": True,
            "statistics": stats,
            "period": {
                "date_from": date_from,
                "date_to": date_to
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка назначения визита: {str(e)}"
        )

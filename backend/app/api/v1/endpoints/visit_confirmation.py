"""
API endpoints для подтверждения визитов через Telegram и PWA
Публичные эндпоинты без авторизации (используют токены)
"""
from datetime import date, datetime
from typing import Optional, Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db
from app.models.user import User
from app.models.patient import Patient
from app.models.visit import Visit, VisitService
from app.models.service import Service
from app.models.clinic import Doctor
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.crud import online_queue as crud_queue
from app.services.confirmation_security import ConfirmationSecurityService

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================

class TelegramConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    telegram_user_id: Optional[str] = None
    telegram_username: Optional[str] = None

class PWAConfirmRequest(BaseModel):
    token: str = Field(..., min_length=10)
    user_agent: Optional[str] = None
    ip_address: Optional[str] = None

class ConfirmationResponse(BaseModel):
    success: bool
    message: str
    visit_id: int
    status: str
    patient_name: str
    visit_date: str
    visit_time: Optional[str]
    queue_numbers: Optional[Dict[str, Any]] = None
    print_tickets: Optional[List[Dict[str, Any]]] = None

# ===================== TELEGRAM ПОДТВЕРЖДЕНИЕ =====================

@router.post("/telegram/visits/confirm", response_model=ConfirmationResponse)
def confirm_visit_by_telegram(
    request: TelegramConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Подтверждение визита через Telegram бот по токену
    Публичный эндпоинт без авторизации
    """
    security_service = ConfirmationSecurityService(db)
    
    try:
        # Проверяем безопасность запроса
        security_check = security_service.validate_confirmation_request(
            token=request.token,
            source_ip=None,  # TODO: получить из request
            user_agent=None,  # TODO: получить из request
            channel="telegram"
        )
        
        if not security_check.allowed:
            # Записываем неудачную попытку
            security_service.record_confirmation_attempt(
                visit_id=0,  # Неизвестен при неудачной валидации
                success=False,
                channel="telegram",
                error_reason=security_check.reason
            )
            
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS if security_check.retry_after else status.HTTP_400_BAD_REQUEST,
                detail=security_check.reason,
                headers={"Retry-After": str(security_check.retry_after)} if security_check.retry_after else None
            )
        
        # Находим визит по токену (повторно, но с дополнительными проверками)
        visit = db.query(Visit).filter(
            Visit.confirmation_token == request.token,
            Visit.status == "pending_confirmation"
        ).first()
        
        if not visit:
            security_service.record_confirmation_attempt(
                visit_id=0,
                success=False,
                channel="telegram",
                error_reason="Visit not found"
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден или уже подтвержден"
            )
        
        # Проверяем что канал подтверждения соответствует
        if visit.confirmation_channel not in ["telegram", "auto"]:
            security_service.record_confirmation_attempt(
                visit_id=visit.id,
                success=False,
                channel="telegram",
                error_reason="Wrong confirmation channel"
            )
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Этот визит нельзя подтвердить через Telegram"
            )
        
        # Подтверждаем визит
        visit.confirmed_at = datetime.utcnow()
        visit.confirmed_by = f"telegram_{request.telegram_user_id or 'unknown'}"
        visit.status = "confirmed"
        
        queue_numbers = {}
        print_tickets = []
        
        # Если визит на сегодня - присваиваем номера в очередях
        if visit.visit_date == date.today():
            queue_numbers, print_tickets = _assign_queue_numbers_on_confirmation(db, visit)
            visit.status = "open"  # Готов к приему
        
        db.commit()
        db.refresh(visit)
        
        # Записываем успешную попытку подтверждения
        security_service.record_confirmation_attempt(
            visit_id=visit.id,
            success=True,
            channel="telegram"
        )
        
        # Получаем данные пациента
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        patient_name = patient.short_name() if patient else "Неизвестный пациент"
        
        return ConfirmationResponse(
            success=True,
            message=f"✅ Визит подтвержден! {'Номера в очередях присвоены.' if queue_numbers else 'Номера будут присвоены утром в день визита.'}",
            visit_id=visit.id,
            status=visit.status,
            patient_name=patient_name,
            visit_date=visit.visit_date.isoformat(),
            visit_time=visit.visit_time,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        # Записываем неудачную попытку при системной ошибке
        try:
            security_service.record_confirmation_attempt(
                visit_id=visit.id if 'visit' in locals() else 0,
                success=False,
                channel="telegram",
                error_reason=f"System error: {str(e)}"
            )
        except:
            pass  # Не прерываем обработку основной ошибки
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подтверждения визита: {str(e)}"
        )

# ===================== PWA ПОДТВЕРЖДЕНИЕ =====================

@router.post("/patient/visits/confirm", response_model=ConfirmationResponse)
def confirm_visit_by_pwa(
    request: PWAConfirmRequest,
    db: Session = Depends(get_db)
):
    """
    Подтверждение визита через PWA приложение по токену
    Публичный эндпоинт без авторизации
    """
    try:
        # Находим визит по токену
        visit = db.query(Visit).filter(
            Visit.confirmation_token == request.token,
            Visit.status == "pending_confirmation"
        ).first()
        
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден или уже подтвержден"
            )
        
        # Проверяем что токен не истек
        if visit.confirmation_expires_at and visit.confirmation_expires_at < datetime.utcnow():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Срок подтверждения истек"
            )
        
        # Проверяем что канал подтверждения соответствует
        if visit.confirmation_channel not in ["pwa", "auto"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Этот визит нельзя подтвердить через PWA"
            )
        
        # Подтверждаем визит
        visit.confirmed_at = datetime.utcnow()
        visit.confirmed_by = f"pwa_{request.ip_address or 'unknown'}"
        visit.status = "confirmed"
        
        queue_numbers = {}
        print_tickets = []
        
        # Если визит на сегодня - присваиваем номера в очередях
        if visit.visit_date == date.today():
            queue_numbers, print_tickets = _assign_queue_numbers_on_confirmation(db, visit)
            visit.status = "open"  # Готов к приему
        
        db.commit()
        db.refresh(visit)
        
        # Получаем данные пациента
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        patient_name = patient.short_name() if patient else "Неизвестный пациент"
        
        return ConfirmationResponse(
            success=True,
            message=f"✅ Визит подтвержден! {'Номера в очередях присвоены.' if queue_numbers else 'Номера будут присвоены утром в день визита.'}",
            visit_id=visit.id,
            status=visit.status,
            patient_name=patient_name,
            visit_date=visit.visit_date.isoformat(),
            visit_time=visit.visit_time,
            queue_numbers=queue_numbers,
            print_tickets=print_tickets
        )
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка подтверждения визита: {str(e)}"
        )

# ===================== ОБЩИЕ ФУНКЦИИ =====================

def _assign_queue_numbers_on_confirmation(db: Session, visit: Visit) -> tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Присваивает номера в очередях при подтверждении визита на сегодня
    Возвращает (queue_numbers, print_tickets)
    """
    # Получаем услуги визита
    visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
    
    # Определяем уникальные queue_tag из услуг
    unique_queue_tags = set()
    for vs in visit_services:
        service = db.query(Service).filter(Service.id == vs.service_id).first()
        if service and service.queue_tag:
            unique_queue_tags.add(service.queue_tag)
    
    if not unique_queue_tags:
        return {}, []
    
    today = date.today()
    queue_numbers = {}
    print_tickets = []
    
    # Получаем настройки очередей
    queue_settings = {}  # Можно загрузить из настроек
    
    for queue_tag in unique_queue_tags:
        # Определяем врача для очереди
        doctor_id = visit.doctor_id
        
        # Для очередей без конкретного врача используем ресурс-врачей
        if queue_tag == "ecg" and not doctor_id:
            ecg_resource = db.query(User).filter(
                User.username == "ecg_resource",
                User.is_active == True
            ).first()
            if ecg_resource:
                doctor_id = ecg_resource.id
            else:
                continue
                
        elif queue_tag == "lab" and not doctor_id:
            lab_resource = db.query(User).filter(
                User.username == "lab_resource",
                User.is_active == True
            ).first()
            if lab_resource:
                doctor_id = lab_resource.id
            else:
                continue
        
        if not doctor_id:
            continue
        
        # Получаем или создаем дневную очередь
        daily_queue = crud_queue.get_or_create_daily_queue(db, today, doctor_id, queue_tag)
        
        # Подсчитываем текущее количество записей в очереди
        current_count = crud_queue.count_queue_entries(db, daily_queue.id)
        start_number = queue_settings.get("start_numbers", {}).get(queue_tag, 1)
        next_number = start_number + current_count
        
        # Создаем запись в очереди
        queue_entry = OnlineQueueEntry(
            queue_id=daily_queue.id,
            patient_id=visit.patient_id,
            number=next_number,
            status="waiting",
            source="confirmation"  # Источник: подтверждение визита
        )
        db.add(queue_entry)
        
        queue_numbers[queue_tag] = {
            "queue_tag": queue_tag,
            "number": next_number,
            "queue_id": daily_queue.id
        }
        
        # Подготавливаем данные для печати талона
        queue_names = {
            "ecg": "ЭКГ",
            "cardiology_common": "Кардиолог",
            "dermatology": "Дерматолог", 
            "stomatology": "Стоматолог",
            "cosmetology": "Косметолог",
            "lab": "Лаборатория",
            "general": "Общая очередь"
        }
        
        doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first() if visit.doctor_id else None
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        
        print_tickets.append({
            "visit_id": visit.id,
            "queue_tag": queue_tag,
            "queue_name": queue_names.get(queue_tag, queue_tag),
            "queue_number": next_number,
            "queue_id": daily_queue.id,
            "patient_id": visit.patient_id,
            "patient_name": patient.short_name() if patient else "Неизвестный пациент",
            "doctor_name": doctor.user.full_name if doctor and doctor.user else "Без врача",
            "department": visit.department,
            "visit_date": visit.visit_date.isoformat(),
            "visit_time": visit.visit_time
        })
    
    return queue_numbers, print_tickets


# ===================== ИНФОРМАЦИОННЫЕ ЭНДПОИНТЫ =====================

@router.get("/visits/info/{token}")
def get_visit_info_by_token(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Получение информации о визите по токену (без подтверждения)
    Для предварительного просмотра перед подтверждением
    """
    try:
        visit = db.query(Visit).filter(
            Visit.confirmation_token == token
        ).first()
        
        if not visit:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Визит не найден"
            )
        
        # Получаем данные пациента
        patient = db.query(Patient).filter(Patient.id == visit.patient_id).first()
        
        # Получаем услуги
        visit_services = db.query(VisitService).filter(VisitService.visit_id == visit.id).all()
        services_info = []
        total_amount = 0
        
        for vs in visit_services:
            services_info.append({
                "name": vs.name,
                "code": vs.code,
                "quantity": vs.qty,
                "price": float(vs.price) if vs.price else 0,
                "total": float(vs.price * vs.qty) if vs.price else 0
            })
            total_amount += float(vs.price * vs.qty) if vs.price else 0
        
        # Получаем врача
        doctor = db.query(Doctor).filter(Doctor.id == visit.doctor_id).first() if visit.doctor_id else None
        doctor_name = doctor.user.full_name if doctor and doctor.user else "Не назначен"
        
        return {
            "visit_id": visit.id,
            "status": visit.status,
            "patient_name": patient.short_name() if patient else "Неизвестный пациент",
            "doctor_name": doctor_name,
            "visit_date": visit.visit_date.isoformat(),
            "visit_time": visit.visit_time,
            "department": visit.department,
            "discount_mode": visit.discount_mode,
            "services": services_info,
            "total_amount": total_amount,
            "currency": "UZS",
            "confirmation_expires_at": visit.confirmation_expires_at.isoformat() if visit.confirmation_expires_at else None,
            "notes": visit.notes
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о визите: {str(e)}"
        )

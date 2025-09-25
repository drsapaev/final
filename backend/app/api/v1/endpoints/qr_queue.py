"""
API эндпоинты для QR очередей
"""
from datetime import date, datetime
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.qr_queue_service import QRQueueService

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================

class QRTokenGenerateRequest(BaseModel):
    """Запрос на генерацию QR токена"""
    specialist_id: int = Field(..., description="ID специалиста")
    department: str = Field(..., description="Отделение")
    expires_hours: int = Field(default=24, ge=1, le=168, description="Время жизни токена в часах")


class QRTokenResponse(BaseModel):
    """Ответ с QR токеном"""
    token: str
    qr_url: str
    qr_code_base64: str
    specialist_id: int
    department: str
    expires_at: str
    active: bool


class QRTokenInfoResponse(BaseModel):
    """Информация о QR токене"""
    token: str
    specialist_id: int
    specialist_name: str
    department: str
    department_name: str
    queue_length: int
    queue_active: bool
    expires_at: str


class JoinSessionStartRequest(BaseModel):
    """Запрос на начало сессии присоединения"""
    token: str = Field(..., description="QR токен")


class JoinSessionStartResponse(BaseModel):
    """Ответ с данными сессии"""
    session_token: str
    expires_at: str
    queue_info: Dict[str, Any]


class JoinSessionCompleteRequest(BaseModel):
    """Запрос на завершение сессии присоединения"""
    session_token: str = Field(..., description="Токен сессии")
    patient_name: str = Field(..., min_length=2, max_length=200, description="ФИО пациента")
    phone: str = Field(..., pattern=r"^\+?[1-9]\d{1,14}$", description="Номер телефона")
    telegram_id: Optional[int] = Field(None, description="Telegram ID")


class JoinSessionCompleteResponse(BaseModel):
    """Ответ с результатом присоединения"""
    success: bool
    queue_number: int
    queue_length: int
    estimated_wait_time: int
    specialist_name: str
    department: str


class QueueStatusResponse(BaseModel):
    """Статус очереди"""
    active: bool
    queue_length: int
    current_number: Optional[int]
    entries: List[Dict[str, Any]]


class CallNextPatientResponse(BaseModel):
    """Ответ на вызов следующего пациента"""
    success: bool
    message: Optional[str] = None
    patient: Optional[Dict[str, Any]] = None
    queue_length: Optional[int] = None


class ActiveQRTokenResponse(BaseModel):
    """Активный QR токен"""
    token: str
    specialist_id: int
    department: str
    created_at: str
    expires_at: str
    sessions_count: int
    successful_joins: int
    qr_url: str


# ===================== ЭНДПОИНТЫ =====================

@router.post("/admin/qr-tokens/generate", response_model=QRTokenResponse)
def generate_qr_token(
    request: QRTokenGenerateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
):
    """
    Генерирует QR токен для присоединения к очереди
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    try:
        result = service.generate_qr_token(
            specialist_id=request.specialist_id,
            department=request.department,
            generated_by_user_id=current_user.id,
            expires_hours=request.expires_hours
        )
        
        return QRTokenResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR токена: {str(e)}"
        )


@router.get("/qr-tokens/{token}/info", response_model=QRTokenInfoResponse)
def get_qr_token_info(
    token: str,
    db: Session = Depends(get_db)
):
    """
    Получает информацию о QR токене (публичный эндпоинт)
    """
    service = QRQueueService(db)
    
    token_info = service.get_qr_token_info(token)
    
    if not token_info:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR токен не найден или истек"
        )
    
    return QRTokenInfoResponse(**token_info)


@router.post("/queue/join/start", response_model=JoinSessionStartResponse)
def start_join_session(
    request: JoinSessionStartRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Начинает сессию присоединения к очереди (публичный эндпоинт)
    """
    service = QRQueueService(db)
    
    try:
        result = service.start_join_session(
            token=request.token,
            ip_address=http_request.client.host if http_request.client else None,
            user_agent=http_request.headers.get("User-Agent")
        )
        
        return JoinSessionStartResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка начала сессии: {str(e)}"
        )


@router.post("/queue/join/complete", response_model=JoinSessionCompleteResponse)
def complete_join_session(
    request: JoinSessionCompleteRequest,
    db: Session = Depends(get_db)
):
    """
    Завершает сессию присоединения к очереди (публичный эндпоинт)
    """
    service = QRQueueService(db)
    
    try:
        result = service.complete_join_session(
            session_token=request.session_token,
            patient_name=request.patient_name,
            phone=request.phone,
            telegram_id=request.telegram_id
        )
        
        return JoinSessionCompleteResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка присоединения к очереди: {str(e)}"
        )


@router.get("/queue/status/{specialist_id}", response_model=QueueStatusResponse)
def get_queue_status(
    specialist_id: int,
    target_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
):
    """
    Получает статус очереди специалиста
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    # Парсим дату если указана
    parsed_date = None
    if target_date:
        try:
            parsed_date = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат даты. Используйте YYYY-MM-DD"
            )
    
    result = service.get_queue_status(specialist_id, parsed_date)
    
    return QueueStatusResponse(**result)


@router.post("/queue/{specialist_id}/call-next", response_model=CallNextPatientResponse)
def call_next_patient(
    specialist_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
):
    """
    Вызывает следующего пациента в очереди
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    try:
        result = service.call_next_patient(specialist_id, current_user.id)
        
        return CallNextPatientResponse(**result)
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка вызова пациента: {str(e)}"
        )


@router.get("/admin/qr-tokens/active", response_model=List[ActiveQRTokenResponse])
def get_active_qr_tokens(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
):
    """
    Получает активные QR токены пользователя
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    tokens = service.get_active_qr_tokens(current_user.id)
    
    return [ActiveQRTokenResponse(**token) for token in tokens]


@router.delete("/admin/qr-tokens/{token}")
def deactivate_qr_token(
    token: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Doctor", "Registrar"))
):
    """
    Деактивирует QR токен
    Доступно администраторам, врачам и регистраторам
    """
    service = QRQueueService(db)
    
    success = service.deactivate_qr_token(token, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="QR токен не найден или вы не являетесь его создателем"
        )
    
    return {"message": "QR токен успешно деактивирован"}


# ===================== СТАТИСТИКА И АНАЛИТИКА =====================

@router.get("/admin/queue-analytics/{specialist_id}")
def get_queue_analytics(
    specialist_id: int,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Получает аналитику по очередям специалиста
    Доступно только администраторам
    """
    # Парсим даты
    start_dt = None
    end_dt = None
    
    if start_date:
        try:
            start_dt = datetime.strptime(start_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат start_date. Используйте YYYY-MM-DD"
            )
    
    if end_date:
        try:
            end_dt = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Неверный формат end_date. Используйте YYYY-MM-DD"
            )
    
    # Если даты не указаны, берем последние 30 дней
    if not start_dt:
        start_dt = date.today() - timedelta(days=30)
    if not end_dt:
        end_dt = date.today()
    
    from app.models.online_queue import QueueStatistics, DailyQueue
    
    # Получаем статистику
    stats = db.query(QueueStatistics).join(DailyQueue).filter(
        DailyQueue.specialist_id == specialist_id,
        QueueStatistics.date >= start_dt,
        QueueStatistics.date <= end_dt
    ).all()
    
    # Агрегируем данные
    total_online_joins = sum(s.online_joins for s in stats)
    total_desk_registrations = sum(s.desk_registrations for s in stats)
    total_telegram_joins = sum(s.telegram_joins for s in stats)
    total_confirmation_joins = sum(s.confirmation_joins for s in stats)
    total_served = sum(s.total_served for s in stats)
    total_no_show = sum(s.total_no_show for s in stats)
    
    avg_wait_time = None
    if stats:
        wait_times = [s.average_wait_time for s in stats if s.average_wait_time]
        if wait_times:
            avg_wait_time = sum(wait_times) / len(wait_times)
    
    return {
        "specialist_id": specialist_id,
        "period": {
            "start_date": start_dt.isoformat(),
            "end_date": end_dt.isoformat()
        },
        "totals": {
            "online_joins": total_online_joins,
            "desk_registrations": total_desk_registrations,
            "telegram_joins": total_telegram_joins,
            "confirmation_joins": total_confirmation_joins,
            "total_served": total_served,
            "total_no_show": total_no_show
        },
        "metrics": {
            "average_wait_time": avg_wait_time,
            "no_show_rate": (total_no_show / (total_served + total_no_show)) * 100 if (total_served + total_no_show) > 0 else 0
        },
        "daily_stats": [
            {
                "date": stat.date.isoformat(),
                "online_joins": stat.online_joins,
                "desk_registrations": stat.desk_registrations,
                "telegram_joins": stat.telegram_joins,
                "confirmation_joins": stat.confirmation_joins,
                "total_served": stat.total_served,
                "total_no_show": stat.total_no_show,
                "average_wait_time": stat.average_wait_time,
                "peak_hour": stat.peak_hour,
                "max_queue_length": stat.max_queue_length
            }
            for stat in stats
        ]
    }

"""
API endpoints для онлайн-очереди согласно detail.md стр. 224-257
"""
from datetime import date, datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.crud import online_queue as crud_queue
from app.services.queue_service import (
    queue_service,
    QueueValidationError,
    QueueNotFoundError,
    QueueConflictError,
)
from app.schemas.online_queue import (
    QRTokenRequest, QRTokenResponse,
    QueueJoinRequest, QueueJoinResponse, QueueJoinError,
    QueueOpenRequest, QueueOpenResponse,
    QueueStatusCheck
)

router = APIRouter()

# ===================== ГЕНЕРАЦИЯ QR ТОКЕНОВ =====================

@router.post("/online-queue/qrcode", response_model=QRTokenResponse)
def generate_qr_token(
    day: date = Query(..., description="Дата в формате YYYY-MM-DD"),
    specialist_id: int = Query(..., description="ID врача/специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Генерация QR токена для онлайн-очереди
    Из detail.md стр. 228: POST /api/online-queue/qrcode?day=YYYY-MM-DD&specialist_id=X → token
    """
    try:
        token, token_data = queue_service.assign_queue_token(
            db,
            specialist_id=specialist_id,
            department=None,
            generated_by_user_id=current_user.id,
            target_date=day,
            is_clinic_wide=False,
        )
        
        # Формируем URL для QR кода
        qr_url = f"/pwa/queue?token={token}"
        
        return QRTokenResponse(
            token=token,
            qr_url=qr_url,
            specialist_name=token_data["specialist_name"],
            specialty=token_data["specialty"],
            cabinet=token_data["cabinet"],
            day=day,
            start_time=token_data["start_time"],
            max_slots=token_data["max_slots"],
            current_count=token_data["current_count"]
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка генерации QR токена: {str(e)}"
        )


# ===================== ВСТУПЛЕНИЕ В ОЧЕРЕДЬ =====================

@router.post("/online-queue/join")
def join_queue(
    request: QueueJoinRequest,
    db: Session = Depends(get_db)
):
    """
    Вступление в онлайн-очередь
    Из detail.md стр. 235: POST /api/online-queue/join { token, phone?, telegram_id? } → номер
    """
    svc = queue_service
    try:
        join_result = svc.join_queue_with_token(
            db,
            token_str=request.token,
            patient_name=request.patient_name,
            phone=request.phone,
            telegram_id=request.telegram_id,
            source="online",
        )
    except QueueValidationError as exc:
        return QueueJoinError(
            success=False,
            error_code="VALIDATION_ERROR",
            message=str(exc),
        )
    except QueueConflictError as exc:
        return QueueJoinError(
            success=False,
            error_code="QUEUE_FULL",
            message=str(exc),
            queue_full=True,
        )
    except QueueNotFoundError as exc:
        return QueueJoinError(
            success=False,
            error_code="QUEUE_NOT_FOUND",
            message=str(exc),
        )
    except Exception as e:
        return QueueJoinError(
            success=False,
            error_code="INTERNAL_ERROR",
            message=f"Ошибка вступления в очередь: {str(e)}"
        )

    entry = join_result["entry"]
    specialist_name = join_result.get("specialist_name")
    cabinet = join_result.get("cabinet")

    if join_result["duplicate"]:
        return QueueJoinResponse(
            success=True,
            number=entry.number,
            duplicate=True,
            message=f"✅ Вы уже записаны по {join_result['duplicate_reason']}. Ваш номер: {entry.number}",
            specialist_name=specialist_name,
            cabinet=cabinet,
            estimated_time="Ожидайте вызова",
        )

    return QueueJoinResponse(
        success=True,
        number=entry.number,
        duplicate=False,
        message=f"Вы записаны в очередь. Ваш номер: {entry.number}",
        specialist_name=specialist_name,
        cabinet=cabinet,
        estimated_time="Придите к открытию приема",
    )


# ===================== ОТКРЫТИЕ ПРИЕМА =====================

@router.post("/online-queue/open", response_model=QueueOpenResponse)
def open_queue(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Открытие приема и закрытие онлайн-набора
    Из detail.md стр. 253: Кнопка «Открыть приём сейчас» → проставляется opened_at → онлайн набор закрыт
    """
    try:
        result = crud_queue.open_daily_queue(
            db=db,
            day=day,
            specialist_id=specialist_id,
            user_id=current_user.id
        )
        
        return QueueOpenResponse(**result)
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка открытия приема: {str(e)}"
        )


# ===================== ПРОВЕРКА СТАТУСА =====================

@router.get("/online-queue/status")
def check_queue_status(
    day: date = Query(..., description="Дата"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db)
):
    """Проверка статуса очереди и доступности"""
    try:
        # Проверяем доступность
        availability = crud_queue.check_queue_availability(db, day, specialist_id)
        
        # Получаем статус очереди
        queue_status = crud_queue.get_queue_status(db, day, specialist_id)
        
        # Получаем настройки
        from app.crud.clinic import get_queue_settings
        queue_settings = get_queue_settings(db)
        
        from zoneinfo import ZoneInfo
        timezone = ZoneInfo(queue_settings.get("timezone", "Asia/Tashkent"))
        current_time = datetime.now(timezone)
        
        return QueueStatusCheck(
            queue_open=queue_status.get("queue_open", False),
            within_hours=availability.get("available", False),
            has_slots=not availability.get("reason") == "QUEUE_FULL",
            current_time=current_time.replace(tzinfo=None),
            queue_start_time=f"{queue_settings.get('queue_start_hour', 7)}:00",
            opened_at=queue_status.get("opened_at")
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка проверки статуса: {str(e)}"
        )


# ===================== ПОЛУЧЕНИЕ ОЧЕРЕДИ =====================

@router.get("/online-queue/today")
def get_today_queue(
    specialist_id: Optional[int] = Query(None, description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Получить очередь на сегодня"""
    try:
        today = date.today()
        
        if specialist_id:
            # Очередь конкретного специалиста
            queue_status = crud_queue.get_queue_status(db, today, specialist_id)
            return queue_status
        else:
            # Статистика по всем очередям
            stats = crud_queue.get_queue_statistics(db, today)
            return stats
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения очереди: {str(e)}"
        )


# ===================== АДМИНИСТРИРОВАНИЕ =====================

@router.get("/online-queue/stats")
def get_queue_stats(
    days_back: int = Query(7, ge=1, le=30, description="Дней назад"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """Статистика онлайн-очередей"""
    try:
        from datetime import timedelta
        
        start_date = date.today() - timedelta(days=days_back)
        
        # Здесь будет детальная статистика
        # Пока возвращаем базовую информацию
        
        return {
            "period_start": start_date,
            "period_end": date.today(),
            "total_tokens_generated": 0,
            "total_queue_entries": 0,
            "by_specialty": {},
            "by_day": {}
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )

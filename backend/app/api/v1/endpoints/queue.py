"""
API endpoints для системы очередей
"""
from datetime import datetime, date
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.models.clinic import Doctor
# from app.models.patient import Patient  # Временно отключено
from app.api.deps import get_current_user
from app.services.queue_service import (
    get_queue_service,
    QueueValidationError,
    QueueNotFoundError,
    QueueConflictError,
)
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

# Timezone для Узбекистана (UTC+5)
TASHKENT_OFFSET = 5

# Pydantic схемы
class QueueTokenResponse(BaseModel):
    token: str
    qr_url: str
    expires_at: datetime
    specialist_name: str
    day: date

class QueueJoinRequest(BaseModel):
    token: str
    phone: Optional[str] = None
    telegram_id: Optional[str] = None
    patient_name: Optional[str] = None

class QueueJoinResponse(BaseModel):
    success: bool
    number: Optional[int] = None
    message: str
    duplicate: bool = False
    queue_info: Optional[dict] = None

class QueueEntryResponse(BaseModel):
    id: int
    number: int
    patient_name: Optional[str]
    phone: Optional[str]
    status: str
    created_at: datetime
    called_at: Optional[datetime]

class QueueStatusResponse(BaseModel):
    queue_id: int
    day: date
    specialist_name: str
    is_open: bool
    opened_at: Optional[datetime]
    total_entries: int
    waiting_entries: int
    entries: List[QueueEntryResponse]


@router.post("/qrcode", response_model=QueueTokenResponse)
def generate_qr_token(
    day: date = Query(..., description="День для очереди (YYYY-MM-DD)"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Генерация QR токена для онлайн-очереди
    Доступно только регистраторам и админам
    """
    try:
        # Проверка прав доступа
        if current_user.role not in ["Admin", "Registrar"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        specialist = db.query(User).filter(
            User.id == specialist_id,
            User.role == "Doctor"
        ).first()
        
        if not specialist:
            raise HTTPException(status_code=404, detail="Специалист не найден")
        
        if day < date.today():
            raise HTTPException(status_code=400, detail="Нельзя создать очередь на прошедший день")

        queue_service = get_queue_service()
        token_value, token_meta = queue_service.assign_queue_token(
            db,
            specialist_id=specialist_id,
            department=None,
            generated_by_user_id=current_user.id,
            target_date=day,
            is_clinic_wide=False,
        )

        qr_url = f"/queue/join?token={token_value}"

        return QueueTokenResponse(
            token=token_value,
            qr_url=qr_url,
            expires_at=token_meta.get("expires_at"),
            specialist_name=token_meta.get("specialist_name") or specialist.full_name or specialist.username,
            day=token_meta.get("day", day)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка генерации QR токена: {str(e)}"
        )


@router.post("/join", response_model=QueueJoinResponse)
def join_queue(
    request: QueueJoinRequest,
    db: Session = Depends(get_db)
):
    """
    Вступление в онлайн-очередь по токену
    Доступно всем (публичный endpoint)
    """
    try:
        queue_service = get_queue_service()
        try:
            join_result = queue_service.join_queue_with_token(
                db,
                token_str=request.token,
                patient_name=request.patient_name,
                phone=request.phone,
                telegram_id=request.telegram_id,
                source="online",
            )
        except (QueueValidationError, QueueNotFoundError, QueueConflictError) as exc:
            return QueueJoinResponse(success=False, message=str(exc))

        queue_entry = join_result["entry"]
        daily_queue = join_result.get("daily_queue")
        specialist_display = (
            daily_queue.specialist.user.full_name
            if daily_queue and daily_queue.specialist and daily_queue.specialist.user
            else join_result.get("specialist_name")
        )
        queue_day = (
            str(daily_queue.day)
            if daily_queue and daily_queue.day
            else queue_entry.queue.day.isoformat()
            if queue_entry.queue and queue_entry.queue.day
            else None
        )

        if join_result["duplicate"]:
            status_text = {
                "waiting": "ожидает вызова",
                "called": "вызван к врачу",
            }.get(queue_entry.status, queue_entry.status)

            return QueueJoinResponse(
                success=True,
                number=queue_entry.number,
                message=f"✅ Вы уже записаны по {join_result['duplicate_reason']}. Ваш номер: {queue_entry.number} ({status_text})",
                duplicate=True,
                queue_info={
                    "specialist": specialist_display,
                    "day": queue_day,
                    "position": queue_entry.number,
                    "status": queue_entry.status,
                    "created_at": queue_entry.created_at.isoformat()
                    if queue_entry.created_at
                    else None,
                    "estimated_time": "Ожидайте вызова",
                },
            )

        try:
            import asyncio
            from app.services.display_websocket import get_display_manager

            async def send_queue_update():
                manager = get_display_manager()
                await manager.broadcast_queue_update(
                    queue_entry=queue_entry,
                    event_type="queue.created"
                )

            asyncio.create_task(send_queue_update())

        except Exception as ws_error:
            print(f"Предупреждение: не удалось отправить обновление очереди: {ws_error}")

        return QueueJoinResponse(
            success=True,
            number=queue_entry.number,
            message=f"Вы записаны в очередь. Ваш номер: {queue_entry.number}",
            duplicate=False,
            queue_info={
                "specialist": specialist_display,
                "day": queue_day,
                "position": queue_entry.number,
                "estimated_time": "Придите к открытию приема"
            }
        )

    except Exception as e:
        logger.error(f"Ошибка при записи в очередь: {str(e)}")
        return QueueJoinResponse(
            success=False,
            message=f"Ошибка сервера: {str(e)}"
        )


@router.get("/statistics/{specialist_id}")
def get_queue_statistics(
    specialist_id: int,
    day: date = Query(default_factory=date.today, description="День для статистики"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получить статистику очереди для специалиста
    """
    try:
        # Валидация specialist_id
        if not isinstance(specialist_id, int) or specialist_id <= 0:
            raise HTTPException(
                status_code=422,
                detail="Некорректный ID специалиста"
            )
        
        # Получаем очередь
        daily_queue = db.query(DailyQueue).filter(
            DailyQueue.day == day,
            DailyQueue.specialist_id == specialist_id
        ).first()
        
        if not daily_queue:
            return {
                "success": False,
                "message": "Очередь не найдена",
                "statistics": {
                    "total_entries": 0,
                    "waiting": 0,
                    "called": 0,
                    "completed": 0,
                    "cancelled": 0,
                    "max_slots": 0,
                    "available_slots": 0,
                    "is_open": False,
                    "opened_at": None
                }
            }
        
        # Используем сервис для получения статистики
        queue_service = get_queue_service()
        stats = queue_service.get_queue_statistics(db, daily_queue)
        
        return {
            "success": True,
            "statistics": stats,
            "specialist": {
                "id": specialist_id,
                "name": daily_queue.specialist.user.full_name if (daily_queue.specialist and daily_queue.specialist.user) else f"Врач #{specialist_id}"
            },
            "day": day.isoformat()
        }
    
    except Exception as e:
        logger.error(f"Ошибка при получении статистики очереди: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка сервера: {str(e)}"
        )


@router.post("/open")
def open_queue(
    day: date = Query(..., description="День очереди"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Открытие приема (закрывает онлайн-запись)
    Доступно только регистраторам и админам
    """
    try:
        # Проверка прав доступа
        if current_user.role not in ["Admin", "Registrar"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")
        
        # Получение или создание очереди
        daily_queue = db.query(DailyQueue).filter(
            DailyQueue.day == day,
            DailyQueue.specialist_id == specialist_id
        ).first()
        
        if not daily_queue:
            # Создаем очередь если её нет
            daily_queue = DailyQueue(
                day=day,
                specialist_id=specialist_id,
                active=True
            )
            db.add(daily_queue)
            db.commit()
            db.refresh(daily_queue)
        
        if daily_queue.opened_at:
            raise HTTPException(status_code=400, detail="Прием уже открыт")
        
        # Открытие приема
        daily_queue.opened_at = datetime.now()
        db.commit()
    
        return {
            "success": True,
            "message": "Прием открыт. Онлайн-запись закрыта",
            "opened_at": daily_queue.opened_at
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка открытия приема: {str(e)}"
        )


@router.get("/today", response_model=QueueStatusResponse)
def get_today_queue(
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получение текущей очереди на сегодня
    """
    try:
        # Валидация specialist_id
        if not isinstance(specialist_id, int) or specialist_id <= 0:
            raise HTTPException(
                status_code=422,
                detail="Некорректный ID специалиста"
            )
        
        # Проверка существования специалиста
        specialist = db.query(Doctor).filter(Doctor.id == specialist_id).first()
        if not specialist:
            raise HTTPException(
                status_code=404,
                detail="Специалист не найден"
            )
        
        today = date.today()
        
        # Получение очереди
        daily_queue = db.query(DailyQueue).filter(
            DailyQueue.day == today,
            DailyQueue.specialist_id == specialist_id
        ).first()
        
        if not daily_queue:
            raise HTTPException(status_code=404, detail="Очередь на сегодня не найдена")
        
        # Получение записей
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == daily_queue.id
        ).order_by(OnlineQueueEntry.number).all()
        
        waiting_count = sum(1 for entry in entries if entry.status == "waiting")
    
        return QueueStatusResponse(
            queue_id=daily_queue.id,
            day=daily_queue.day,
            specialist_name=(daily_queue.specialist.user.full_name or daily_queue.specialist.user.username) if (daily_queue.specialist and daily_queue.specialist.user) else f"Врач #{daily_queue.specialist_id}",
            is_open=daily_queue.opened_at is not None,
            opened_at=daily_queue.opened_at,
            total_entries=len(entries),
            waiting_entries=waiting_count,
            entries=[
                QueueEntryResponse(
                    id=entry.id,
                    number=entry.number,
                    patient_name=entry.patient_name,
                    phone=entry.phone,
                    status=entry.status,
                    created_at=entry.created_at,
                    called_at=entry.called_at
                ) for entry in entries
            ]
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка получения очереди: {str(e)}"
        )


@router.post("/call/{entry_id}")
def call_patient(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Вызов пациента (для табло)
    """
    # Проверка прав доступа
    if current_user.role not in ["Admin", "Registrar", "Doctor"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    entry = db.query(OnlineQueueEntry).filter(OnlineQueueEntry.id == entry_id).first()
    
    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    
    if entry.status != "waiting":
        raise HTTPException(status_code=400, detail="Пациент уже вызван или обслужен")
    
    # Обновление статуса
    entry.status = "called"
    entry.called_at = datetime.now()
    
    db.commit()
    
    # Отправка WebSocket события для табло
    try:
        import asyncio
        from app.services.display_websocket import get_display_manager
        
        async def send_to_display():
            manager = get_display_manager()
            specialist_name = entry.queue.specialist.full_name if entry.queue.specialist else f"Специалист #{entry.queue.specialist_id}"
            
            await manager.broadcast_patient_call(
                queue_entry=entry,
                doctor_name=specialist_name,
                cabinet=None  # TODO: Добавить кабинет в модель
            )
        
        # Запускаем асинхронную отправку в фоне
        asyncio.create_task(send_to_display())
        
    except Exception as ws_error:
        # Не прерываем основной процесс если WebSocket не работает
        print(f"Предупреждение: не удалось отправить на табло: {ws_error}")
    
    return {
        "success": True,
        "message": f"Пациент №{entry.number} вызван",
        "entry": {
            "id": entry.id,
            "number": entry.number,
            "patient_name": entry.patient_name,
            "called_at": entry.called_at
        }
    }
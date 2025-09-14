"""
API endpoints для системы очередей
"""
from datetime import datetime, date, time, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.models.online_queue import DailyQueue, OnlineQueueEntry, QueueToken
from app.models.user import User
# from app.models.patient import Patient  # Временно отключено
from app.api.deps import get_current_user
from app.services.queue_service import get_queue_service
from pydantic import BaseModel
import uuid
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
    # Проверка прав доступа
    if current_user.role not in ["Admin", "Registrar"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    # Проверка существования специалиста
    specialist = db.query(User).filter(
        User.id == specialist_id,
        User.role == "Doctor"
    ).first()
    
    if not specialist:
        raise HTTPException(status_code=404, detail="Специалист не найден")
    
    # Проверка даты (не в прошлом)
    if day < date.today():
        raise HTTPException(status_code=400, detail="Нельзя создать очередь на прошедший день")
    
    # Создание или получение очереди на день
    daily_queue = db.query(DailyQueue).filter(
        DailyQueue.day == day,
        DailyQueue.specialist_id == specialist_id
    ).first()
    
    if not daily_queue:
        # Получаем правильный стартовый номер для специалиста
        queue_service = get_queue_service()
        start_number = queue_service.get_start_number_for_specialist(specialist)
        
        daily_queue = DailyQueue(
            day=day,
            specialist_id=specialist_id,
            active=True,
            start_number=start_number,
            max_online_slots=queue_service.DEFAULT_MAX_SLOTS
        )
        db.add(daily_queue)
        db.commit()
        db.refresh(daily_queue)
    
    # Генерация токена
    token_str = str(uuid.uuid4())
    expires_at = datetime.combine(day, time(23, 59, 59))  # До конца дня
    
    # Проверка существующего токена
    existing_token = db.query(QueueToken).filter(
        QueueToken.day == day,
        QueueToken.specialist_id == specialist_id,
        QueueToken.expires_at > datetime.now()
    ).first()
    
    if existing_token:
        token_str = existing_token.token
    else:
        queue_token = QueueToken(
            token=token_str,
            day=day,
            specialist_id=specialist_id,
            expires_at=expires_at
        )
        db.add(queue_token)
        db.commit()

    # Формирование QR URL
    qr_url = f"/queue/join?token={token_str}"
    
    return QueueTokenResponse(
        token=token_str,
        qr_url=qr_url,
        expires_at=expires_at,
        specialist_name=specialist.full_name or specialist.username,
        day=day
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
    # Проверка токена
    token = db.query(QueueToken).filter(
        QueueToken.token == request.token,
        QueueToken.expires_at > datetime.now()
    ).first()
    
    if not token:
        return QueueJoinResponse(
            success=False,
            message="Недействительный или истекший токен"
        )
    
    # Получение очереди
    daily_queue = db.query(DailyQueue).filter(
        DailyQueue.day == token.day,
        DailyQueue.specialist_id == token.specialist_id
    ).first()
    
    if not daily_queue:
        return QueueJoinResponse(
            success=False,
            message="Очередь не найдена"
        )
    
    # Получаем сервис очереди
    queue_service = get_queue_service()
    
    # Валидация данных
    is_valid, validation_message = queue_service.validate_queue_entry_data(
        request.patient_name, request.phone, request.telegram_id
    )
    if not is_valid:
        return QueueJoinResponse(success=False, message=validation_message)
    
    # Проверка временного окна
    time_allowed, time_message = queue_service.check_queue_time_window(
        token.day, daily_queue.opened_at
    )
    if not time_allowed:
        return QueueJoinResponse(success=False, message=time_message)
    
    # Проверка лимитов
    limits_ok, limits_message = queue_service.check_queue_limits(db, daily_queue)
    if not limits_ok:
        return QueueJoinResponse(success=False, message=limits_message)
    
    # Проверка уникальности
    existing_entry, duplicate_reason = queue_service.check_uniqueness(
        db, daily_queue, request.phone, request.telegram_id
    )
    
    if existing_entry:
        # Возвращаем существующий номер с подробной информацией
        status_text = {
            "waiting": "ожидает вызова",
            "called": "вызван к врачу"
        }.get(existing_entry.status, existing_entry.status)
        
        return QueueJoinResponse(
            success=True,
            number=existing_entry.number,
            message=f"✅ Вы уже записаны по {duplicate_reason}. Ваш номер: {existing_entry.number} ({status_text})",
            duplicate=True,
            queue_info={
                "specialist": daily_queue.specialist.full_name,
                "day": str(daily_queue.day),
                "position": existing_entry.number,
                "status": existing_entry.status,
                "created_at": existing_entry.created_at.isoformat(),
                "estimated_time": f"Записались в {existing_entry.created_at.strftime('%H:%M')}"
            }
        )
    
    # Создание новой записи
    # Вычисляем следующий номер через сервис
    next_number = queue_service.calculate_next_number(db, daily_queue)
    
    queue_entry = OnlineQueueEntry(
        queue_id=daily_queue.id,
        number=next_number,
        patient_name=request.patient_name,
        phone=request.phone,
        telegram_id=request.telegram_id,
        source="online",
        status="waiting"
    )
    
    db.add(queue_entry)
    
    # Увеличиваем счетчик использований токена
    token.current_uses += 1
    
    db.commit()
    db.refresh(queue_entry)
    
    # Отправка WebSocket события о новой записи
    try:
        import asyncio
        from app.services.display_websocket import get_display_manager
        
        async def send_queue_update():
            manager = get_display_manager()
            await manager.broadcast_queue_update(
                queue_entry=queue_entry,
                event_type="queue.created"
            )
        
        # Запускаем асинхронную отправку в фоне
        asyncio.create_task(send_queue_update())
        
    except Exception as ws_error:
        print(f"Предупреждение: не удалось отправить обновление очереди: {ws_error}")
    
    return QueueJoinResponse(
        success=True,
        number=next_number,
        message=f"Вы записаны в очередь. Ваш номер: {next_number}",
        duplicate=False,
        queue_info={
            "specialist": daily_queue.specialist.full_name,
            "day": str(daily_queue.day),
            "position": next_number,
            "estimated_time": "Придите к открытию приема"
        }
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
            "name": daily_queue.specialist.full_name if daily_queue.specialist else f"Врач #{specialist_id}"
        },
        "day": day.isoformat()
    }


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
    # Проверка прав доступа
    if current_user.role not in ["Admin", "Registrar"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")
    
    # Получение очереди
    daily_queue = db.query(DailyQueue).filter(
        DailyQueue.day == day,
        DailyQueue.specialist_id == specialist_id
    ).first()
    
    if not daily_queue:
        raise HTTPException(status_code=404, detail="Очередь не найдена")
    
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


@router.get("/today", response_model=QueueStatusResponse)
def get_today_queue(
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получение текущей очереди на сегодня
    """
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
        specialist_name=daily_queue.specialist.full_name or daily_queue.specialist.username,
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
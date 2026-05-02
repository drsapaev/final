"""
API endpoints для системы очередей

⚠️ DEPRECATED: Этот модуль содержит legacy endpoints.
Для новых интеграций используйте:
- qr_queue.py - расширенная QR функциональность (/queue/qr-tokens/*, /queue/join/*)
- queue_reorder.py - переупорядочение очереди (/queue/reorder/*)

Этот модуль сохранен для обратной совместимости и будет удален в будущих версиях.
"""

import logging
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

# from app.models.patient import Patient  # Временно отключено
from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.services.queue_api_service import QueueApiService
from app.services.queue_service import (
    get_queue_service,
    QueueConflictError,
    QueueNotFoundError,
    QueueValidationError,
)

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
    current_user: User = Depends(get_current_user),
):
    """
    Генерация QR токена для онлайн-очереди
    Доступно только регистраторам и админам

    ⚠️ DEPRECATED: Этот endpoint устарел и будет удален в будущих версиях.
    Используйте вместо него: POST /api/v1/queue/admin/qr-tokens/generate

    См. документацию: docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md
    """
    try:
        queue_api_service = QueueApiService(db)

        # Проверка прав доступа
        if current_user.role not in ["Admin", "Registrar"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        specialist = queue_api_service.get_doctor_user(specialist_id)

        if not specialist:
            raise HTTPException(status_code=404, detail="Специалист не найден")

        if day < date.today():
            raise HTTPException(
                status_code=400, detail="Нельзя создать очередь на прошедший день"
            )

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
            specialist_name=token_meta.get("specialist_name")
            or specialist.full_name
            or specialist.username,
            day=token_meta.get("day", day),
        )
    except HTTPException:
        raise
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


@router.post("/join", response_model=QueueJoinResponse)
def join_queue(request: QueueJoinRequest, db: Session = Depends(get_db)):
    """
    Вступление в онлайн-очередь по токену
    Доступно всем (публичный endpoint)

    ⚠️ DEPRECATED: Этот endpoint устарел и будет удален в будущих версиях.
    Используйте вместо него:
    - POST /api/v1/queue/join/start (начало сессии)
    - POST /api/v1/queue/join/complete (завершение присоединения)

    См. документацию: docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md
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
            else (
                queue_entry.queue.day.isoformat()
                if queue_entry.queue and queue_entry.queue.day
                else None
            )
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
                    "created_at": (
                        queue_entry.created_at.isoformat()
                        if queue_entry.created_at
                        else None
                    ),
                    "estimated_time": "Ожидайте вызова",
                },
            )

        try:
            import asyncio

            from app.services.display_websocket import get_display_manager

            async def send_queue_update():
                manager = get_display_manager()
                await manager.broadcast_queue_update(
                    queue_entry=queue_entry, event_type="queue.created"
                )

            asyncio.create_task(send_queue_update())

        except Exception as ws_error:
            logger.warning(
                "Не удалось отправить обновление очереди: %s", ws_error, exc_info=True
            )

        return QueueJoinResponse(
            success=True,
            number=queue_entry.number,
            message=f"Вы записаны в очередь. Ваш номер: {queue_entry.number}",
            duplicate=False,
            queue_info={
                "specialist": specialist_display,
                "day": queue_day,
                "position": queue_entry.number,
                "estimated_time": "Придите к открытию приема",
            },
        )

    except Exception as e:
        logger.error(f"Ошибка при записи в очередь: {str(e)}")
        return QueueJoinResponse(success=False, message=f"Ошибка сервера: {str(e)}")


@router.get("/statistics/{specialist_id}")
def get_queue_statistics(
    specialist_id: int,
    day: date = Query(default_factory=date.today, description="День для статистики"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получить статистику очереди для специалиста

    ⚠️ DEPRECATED: Этот endpoint устарел и будет удален в будущих версиях.
    Используйте вместо него: GET /api/v1/queue/admin/queue-analytics/{specialist_id}

    См. документацию: docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md
    """
    # Валидация specialist_id
    if not isinstance(specialist_id, int) or specialist_id <= 0:
        raise HTTPException(status_code=422, detail="Некорректный ID специалиста")

    # Получаем очередь
    daily_queue = QueueApiService(db).get_daily_queue(
        day=day,
        specialist_id=specialist_id,
    )

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
                "opened_at": None,
            },
        }

    # Используем сервис для получения статистики
    queue_service = get_queue_service()
    stats = queue_service.get_queue_statistics(db, daily_queue)

    return {
        "success": True,
        "statistics": stats,
        "specialist": {
            "id": specialist_id,
            "name": (
                daily_queue.specialist.user.full_name
                if (daily_queue.specialist and daily_queue.specialist.user)
                else f"Врач #{specialist_id}"
            ),
        },
        "day": day.isoformat(),
    }


@router.post("/open")
def open_queue(
    day: date = Query(..., description="День очереди"),
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Открытие приема (закрывает онлайн-запись)
    Доступно только регистраторам и админам

    ⚠️ DEPRECATED: Этот endpoint устарел и будет удален в будущих версиях.
    Проверьте документацию для альтернативных endpoints.

    См. документацию: docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md
    """
    try:
        queue_api_service = QueueApiService(db)

        # Проверка прав доступа
        if current_user.role not in ["Admin", "Registrar"]:
            raise HTTPException(status_code=403, detail="Недостаточно прав")

        # Получение или создание очереди
        daily_queue = queue_api_service.get_or_create_daily_queue(
            day=day,
            specialist_id=specialist_id,
        )

        if daily_queue.opened_at:
            raise HTTPException(status_code=400, detail="Прием уже открыт")

        # Открытие приема
        queue_api_service.open_daily_queue(daily_queue)

        return {
            "success": True,
            "message": "Прием открыт. Онлайн-запись закрыта",
            "opened_at": daily_queue.opened_at,
        }
    except HTTPException:
        raise
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


@router.get("/today", response_model=QueueStatusResponse)
def get_today_queue(
    specialist_id: int = Query(..., description="ID специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получение текущей очереди на сегодня

    ⚠️ DEPRECATED: Этот endpoint устарел и будет удален в будущих версиях.
    Используйте вместо него: GET /api/v1/queue/status/{specialist_id}

    См. документацию: docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md
    """
    # Валидация specialist_id
    if not isinstance(specialist_id, int) or specialist_id <= 0:
        raise HTTPException(status_code=422, detail="Некорректный ID специалиста")

    # Проверка существования специалиста
    queue_api_service = QueueApiService(db)
    specialist = queue_api_service.get_doctor(specialist_id)
    if not specialist:
        raise HTTPException(status_code=404, detail="Специалист не найден")

    today = date.today()

    # Получение очереди
    daily_queue = queue_api_service.get_daily_queue(
        day=today,
        specialist_id=specialist_id,
    )

    if not daily_queue:
        raise HTTPException(status_code=404, detail="Очередь на сегодня не найдена")

    # Получение записей
    entries = queue_api_service.list_queue_entries(queue_id=daily_queue.id)

    waiting_count = sum(1 for entry in entries if entry.status == "waiting")

    return QueueStatusResponse(
        queue_id=daily_queue.id,
        day=daily_queue.day,
        specialist_name=(
            (
                daily_queue.specialist.user.full_name
                or daily_queue.specialist.user.username
            )
            if (daily_queue.specialist and daily_queue.specialist.user)
            else f"Врач #{daily_queue.specialist_id}"
        ),
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
                called_at=entry.called_at,
            )
            for entry in entries
        ],
    )
    # Остальные исключения обрабатываются централизованными обработчиками
    # (exception_handlers.py)


@router.post("/call/{entry_id}")
def call_patient(
    entry_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Вызов пациента (для табло)

    ⚠️ DEPRECATED: Этот endpoint устарел и будет удален в будущих версиях.
    Используйте вместо него: POST /api/v1/queue/{specialist_id}/call-next

    См. документацию: docs/QUEUE_ENDPOINTS_MIGRATION_GUIDE.md
    """
    # Проверка прав доступа
    if current_user.role not in ["Admin", "Registrar", "Doctor"]:
        raise HTTPException(status_code=403, detail="Недостаточно прав")

    queue_api_service = QueueApiService(db)
    entry = queue_api_service.get_queue_entry(entry_id)

    if not entry:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    if entry.status != "waiting":
        raise HTTPException(status_code=400, detail="Пациент уже вызван или обслужен")

    # Обновление статуса
    queue_api_service.mark_entry_called(entry)

    # Отправка WebSocket события для табло
    try:
        import asyncio

        from app.services.display_websocket import get_display_manager

        async def send_to_display():
            manager = get_display_manager()
            specialist_name = (
                entry.queue.specialist.full_name
                if entry.queue.specialist
                else f"Специалист #{entry.queue.specialist_id}"
            )

            await manager.broadcast_patient_call(
                queue_entry=entry,
                doctor_name=specialist_name,
                cabinet=None,  # TODO: Добавить кабинет в модель
            )

        # Запускаем асинхронную отправку в фоне
        asyncio.create_task(send_to_display())

    except Exception as ws_error:
        # Не прерываем основной процесс если WebSocket не работает
        logger.warning("Не удалось отправить на табло: %s", ws_error, exc_info=True)

    return {
        "success": True,
        "message": f"Пациент №{entry.number} вызван",
        "entry": {
            "id": entry.id,
            "number": entry.number,
            "patient_name": entry.patient_name,
            "called_at": entry.called_at,
        },
    }

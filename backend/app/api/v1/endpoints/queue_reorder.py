"""
API endpoints для изменения порядка очереди
"""

import logging
from datetime import date
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.user import User
from app.services.queue_reorder_api_service import (
    QueueReorderApiDomainError,
    QueueReorderApiService,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class QueueReorderRequest(BaseModel):
    """Запрос на изменение порядка очереди"""

    queue_id: int
    entry_orders: List[Dict[str, int]]  # [{"entry_id": 1, "new_position": 2}, ...]

    @field_validator('entry_orders')
    @classmethod
    def validate_entry_orders(cls, v: List[Dict[str, int]]) -> List[Dict[str, int]]:
        if not v:
            raise ValueError('Список изменений не может быть пустым')

        # Проверяем, что все позиции уникальны
        positions = [item.get('new_position') for item in v]
        if len(positions) != len(set(positions)):
            raise ValueError('Позиции должны быть уникальными')

        # Проверяем, что позиции начинаются с 1
        if min(positions) < 1:
            raise ValueError('Позиции должны начинаться с 1')

        return v


class QueueReorderResponse(BaseModel):
    """Ответ на изменение порядка очереди"""

    success: bool
    message: str
    updated_entries: int
    queue_info: Dict[str, Any]


class QueueEntryMoveRequest(BaseModel):
    """Запрос на перемещение одной записи в очереди"""

    entry_id: int
    new_position: int

    @field_validator('new_position')
    @classmethod
    def validate_new_position(cls, v: int) -> int:
        if v < 1:
            raise ValueError('Позиция должна быть больше 0')
        return v


@router.put("/reorder", response_model=QueueReorderResponse)
async def reorder_queue(
    request: QueueReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """
    Изменение порядка нескольких записей в очереди
    Доступно администраторам, регистраторам и врачам
    """
    try:
        queue_api_service = QueueReorderApiService(db)
        updated_count, queue_info = queue_api_service.reorder_queue(
            queue_id=request.queue_id,
            entry_orders=request.entry_orders,
            current_user=current_user,
        )

        return QueueReorderResponse(
            success=True,
            message=f"Порядок очереди обновлен. Изменено записей: {updated_count}",
            updated_entries=updated_count,
            queue_info=queue_info,
        )

    except QueueReorderApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering queue: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка изменения порядка очереди: {str(e)}",
        )


@router.put("/move-entry", response_model=QueueReorderResponse)
async def move_queue_entry(
    request: QueueEntryMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"])),
):
    """
    Перемещение одной записи в очереди на новую позицию
    Автоматически сдвигает остальные записи
    """
    try:
        queue_api_service = QueueReorderApiService(db)
        message, updated_count, queue_info = queue_api_service.move_queue_entry(
            entry_id=request.entry_id,
            new_position=request.new_position,
            current_user=current_user,
        )

        return QueueReorderResponse(
            success=True,
            message=message,
            updated_entries=updated_count,
            queue_info=queue_info,
        )

    except QueueReorderApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving queue entry: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка перемещения записи в очереди: {str(e)}",
        )


@router.get("/status/by-specialist/")
async def get_queue_status_by_specialist(
    specialist_id: int,
    day: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получение текущего состояния очереди по специалисту и дню
    """
    try:
        return QueueReorderApiService(db).get_queue_status_by_specialist(
            specialist_id=specialist_id,
            day=day,
        )

    except QueueReorderApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue status by specialist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения состояния очереди: {str(e)}",
        )


@router.get("/status/{queue_id}")
async def get_queue_status(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Получение текущего состояния очереди по ID
    """
    try:
        return QueueReorderApiService(db).get_queue_status(queue_id=queue_id)

    except QueueReorderApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения состояния очереди: {str(e)}",
        )

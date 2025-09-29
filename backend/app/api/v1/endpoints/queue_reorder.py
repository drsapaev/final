"""
API endpoints для изменения порядка очереди
"""
from datetime import datetime, date
from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, validator
import logging

from app.db.session import get_db
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.user import User
from app.api.deps import get_current_user, require_roles
from app.services.queue_service import get_queue_service

logger = logging.getLogger(__name__)
router = APIRouter()


class QueueReorderRequest(BaseModel):
    """Запрос на изменение порядка очереди"""
    queue_id: int
    entry_orders: List[Dict[str, int]]  # [{"entry_id": 1, "new_position": 2}, ...]
    
    @validator('entry_orders')
    def validate_entry_orders(cls, v):
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
    
    @validator('new_position')
    def validate_new_position(cls, v):
        if v < 1:
            raise ValueError('Позиция должна быть больше 0')
        return v


@router.put("/reorder", response_model=QueueReorderResponse)
async def reorder_queue(
    request: QueueReorderRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """
    Изменение порядка нескольких записей в очереди
    Доступно администраторам, регистраторам и врачам
    """
    try:
        # Проверяем существование очереди
        queue = db.query(DailyQueue).filter(DailyQueue.id == request.queue_id).first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Очередь не найдена"
            )
        
        # Проверяем права доступа к очереди
        if current_user.role == "Doctor" and queue.specialist_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для изменения этой очереди"
            )
        
        # Получаем все записи очереди
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == request.queue_id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).order_by(OnlineQueueEntry.number).all()
        
        if not entries:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="В очереди нет активных записей"
            )
        
        # Создаем мапу entry_id -> entry
        entry_map = {entry.id: entry for entry in entries}
        
        # Проверяем, что все entry_id из запроса существуют
        request_entry_ids = {item['entry_id'] for item in request.entry_orders}
        existing_entry_ids = set(entry_map.keys())
        
        if not request_entry_ids.issubset(existing_entry_ids):
            missing_ids = request_entry_ids - existing_entry_ids
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Записи с ID {missing_ids} не найдены в очереди"
            )
        
        # Проверяем диапазон позиций
        max_position = len(entries)
        for item in request.entry_orders:
            if item['new_position'] > max_position:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Позиция {item['new_position']} превышает размер очереди ({max_position})"
                )
        
        # Применяем изменения
        updated_count = 0
        for item in request.entry_orders:
            entry = entry_map[item['entry_id']]
            old_position = entry.number
            new_position = item['new_position']
            
            if old_position != new_position:
                entry.number = new_position
                updated_count += 1
                
                logger.info(
                    f"Queue reorder: Entry {entry.id} moved from position {old_position} "
                    f"to {new_position} by user {current_user.id}"
                )
        
        # Сохраняем изменения
        db.commit()
        
        # Обновляем информацию об очереди
        updated_entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == request.queue_id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).order_by(OnlineQueueEntry.number).all()
        
        queue_info = {
            "queue_id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_name": queue.specialist.full_name if queue.specialist else "Неизвестно",
            "total_entries": len(updated_entries),
            "entries": [
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "status": entry.status,
                    "source": entry.source
                }
                for entry in updated_entries
            ]
        }
        
        return QueueReorderResponse(
            success=True,
            message=f"Порядок очереди обновлен. Изменено записей: {updated_count}",
            updated_entries=updated_count,
            queue_info=queue_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error reordering queue: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка изменения порядка очереди: {str(e)}"
        )


@router.put("/move-entry", response_model=QueueReorderResponse)
async def move_queue_entry(
    request: QueueEntryMoveRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(["Admin", "Registrar", "Doctor"]))
):
    """
    Перемещение одной записи в очереди на новую позицию
    Автоматически сдвигает остальные записи
    """
    try:
        # Находим запись
        entry = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.id == request.entry_id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).first()
        
        if not entry:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Запись в очереди не найдена"
            )
        
        # Проверяем права доступа к очереди
        queue = db.query(DailyQueue).filter(DailyQueue.id == entry.queue_id).first()
        if current_user.role == "Doctor" and queue.specialist_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Нет прав для изменения этой очереди"
            )
        
        # Получаем все записи очереди
        all_entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == entry.queue_id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).order_by(OnlineQueueEntry.number).all()
        
        if request.new_position > len(all_entries):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Позиция {request.new_position} превышает размер очереди ({len(all_entries)})"
            )
        
        old_position = entry.number
        new_position = request.new_position
        
        if old_position == new_position:
            return QueueReorderResponse(
                success=True,
                message="Позиция не изменилась",
                updated_entries=0,
                queue_info={
                    "queue_id": queue.id,
                    "day": queue.day.isoformat(),
                    "specialist_name": queue.specialist.full_name if queue.specialist else "Неизвестно",
                    "total_entries": len(all_entries),
                    "entries": []
                }
            )
        
        # Логика перемещения
        updated_count = 0
        
        if old_position < new_position:
            # Перемещение вниз: сдвигаем записи между old_position+1 и new_position вверх
            for other_entry in all_entries:
                if other_entry.id == entry.id:
                    continue
                if old_position < other_entry.number <= new_position:
                    other_entry.number -= 1
                    updated_count += 1
        else:
            # Перемещение вверх: сдвигаем записи между new_position и old_position-1 вниз
            for other_entry in all_entries:
                if other_entry.id == entry.id:
                    continue
                if new_position <= other_entry.number < old_position:
                    other_entry.number += 1
                    updated_count += 1
        
        # Устанавливаем новую позицию для перемещаемой записи
        entry.number = new_position
        updated_count += 1
        
        # Сохраняем изменения
        db.commit()
        
        logger.info(
            f"Queue entry move: Entry {entry.id} moved from position {old_position} "
            f"to {new_position} by user {current_user.id}"
        )
        
        # Получаем обновленную информацию об очереди
        updated_entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == entry.queue_id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).order_by(OnlineQueueEntry.number).all()
        
        queue_info = {
            "queue_id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_name": queue.specialist.full_name if queue.specialist else "Неизвестно",
            "total_entries": len(updated_entries),
            "entries": [
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "status": entry.status,
                    "source": entry.source
                }
                for entry in updated_entries
            ]
        }
        
        return QueueReorderResponse(
            success=True,
            message=f"Запись перемещена с позиции {old_position} на позицию {new_position}",
            updated_entries=updated_count,
            queue_info=queue_info
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error moving queue entry: {e}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка перемещения записи в очереди: {str(e)}"
        )


@router.get("/status/by-specialist/")
async def get_queue_status_by_specialist(
    specialist_id: int,
    day: date,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получение текущего состояния очереди по специалисту и дню
    """
    try:
        # Находим очередь
        queue = db.query(DailyQueue).filter(
            DailyQueue.specialist_id == specialist_id,
            DailyQueue.day == day
        ).first()
        
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Очередь не найдена"
            )
        
        # Получаем записи очереди
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue.id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).order_by(OnlineQueueEntry.number).all()
        
        return {
            "queue_id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_name": queue.specialist.full_name if queue.specialist else "Неизвестно",
            "specialist_id": queue.specialist_id,
            "is_active": queue.active,
            "opened_at": queue.opened_at.isoformat() if queue.opened_at else None,
            "total_entries": len(entries),
            "entries": [
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat(),
                    "called_at": entry.called_at.isoformat() if entry.called_at else None
                }
                for entry in entries
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue status by specialist: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения состояния очереди: {str(e)}"
        )


@router.get("/status/{queue_id}")
async def get_queue_status(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Получение текущего состояния очереди по ID
    """
    try:
        # Проверяем существование очереди
        queue = db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Очередь не найдена"
            )
        
        # Получаем записи очереди
        entries = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue_id,
            OnlineQueueEntry.status.in_(["waiting", "called"])
        ).order_by(OnlineQueueEntry.number).all()
        
        return {
            "queue_id": queue.id,
            "day": queue.day.isoformat(),
            "specialist_name": queue.specialist.full_name if queue.specialist else "Неизвестно",
            "specialist_id": queue.specialist_id,
            "is_active": queue.active,
            "opened_at": queue.opened_at.isoformat() if queue.opened_at else None,
            "total_entries": len(entries),
            "entries": [
                {
                    "id": entry.id,
                    "number": entry.number,
                    "patient_name": entry.patient_name,
                    "phone": entry.phone,
                    "status": entry.status,
                    "source": entry.source,
                    "created_at": entry.created_at.isoformat(),
                    "called_at": entry.called_at.isoformat() if entry.called_at else None
                }
                for entry in entries
            ]
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting queue status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения состояния очереди: {str(e)}"
        )

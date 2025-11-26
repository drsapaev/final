"""
API endpoints для управления информацией о кабинетах в очередях
"""

import logging
from datetime import date, datetime
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.api.deps import get_db, require_roles, get_current_user
from app.models.user import User
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.clinic import Doctor
from app.crud import online_queue as crud_queue

logger = logging.getLogger(__name__)

router = APIRouter()

# ===================== МОДЕЛИ ДАННЫХ =====================

class CabinetInfo(BaseModel):
    cabinet_number: Optional[str] = None
    cabinet_floor: Optional[int] = None
    cabinet_building: Optional[str] = None

class QueueCabinetUpdateRequest(BaseModel):
    queue_id: int
    cabinet_info: CabinetInfo

class QueueCabinetResponse(BaseModel):
    id: int
    day: str
    specialist_id: int
    specialist_name: str
    queue_tag: Optional[str]
    cabinet_number: Optional[str]
    cabinet_floor: Optional[int]
    cabinet_building: Optional[str]
    entries_count: int
    active: bool

class BulkCabinetUpdateRequest(BaseModel):
    updates: List[QueueCabinetUpdateRequest]

# ===================== ПОЛУЧЕНИЕ ИНФОРМАЦИИ О КАБИНЕТАХ =====================

@router.get("/queues/cabinet-info", response_model=List[QueueCabinetResponse])
def get_queues_cabinet_info(
    day: Optional[str] = Query(None, description="Дата в формате YYYY-MM-DD"),
    specialist_id: Optional[int] = Query(None, description="ID специалиста"),
    cabinet_number: Optional[str] = Query(None, description="Номер кабинета"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """
    Получить информацию о кабинетах для очередей
    """
    try:
        # Строим запрос
        query = db.query(DailyQueue)
        
        # Фильтры
        if day:
            try:
                day_obj = datetime.strptime(day, "%Y-%m-%d").date()
                query = query.filter(DailyQueue.day == day_obj)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD"
                )
        
        if specialist_id:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        
        if cabinet_number:
            query = query.filter(DailyQueue.cabinet_number == cabinet_number)
        
        # Получаем очереди
        queues = query.order_by(DailyQueue.day.desc(), DailyQueue.specialist_id).all()
        
        result = []
        for queue in queues:
            # Получаем информацию о специалисте
            specialist = db.query(Doctor).filter(Doctor.id == queue.specialist_id).first()
            specialist_name = specialist.user.full_name if (specialist and specialist.user) else f"Специалист #{queue.specialist_id}"
            
            # Подсчитываем записи в очереди
            entries_count = db.query(OnlineQueueEntry).filter(
                OnlineQueueEntry.queue_id == queue.id
            ).count()
            
            result.append(QueueCabinetResponse(
                id=queue.id,
                day=queue.day.isoformat(),
                specialist_id=queue.specialist_id,
                specialist_name=specialist_name,
                queue_tag=queue.queue_tag,
                cabinet_number=queue.cabinet_number,
                cabinet_floor=queue.cabinet_floor,
                cabinet_building=queue.cabinet_building,
                entries_count=entries_count,
                active=queue.active
            ))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о кабинетах: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о кабинетах: {str(e)}"
        )


@router.get("/queues/{queue_id}/cabinet-info")
def get_queue_cabinet_info(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor"))
):
    """
    Получить информацию о кабинете для конкретной очереди
    """
    try:
        queue = db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
        
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Очередь не найдена"
            )
        
        # Получаем информацию о специалисте
        specialist = db.query(Doctor).filter(Doctor.id == queue.specialist_id).first()
        specialist_name = specialist.user.full_name if (specialist and specialist.user) else f"Специалист #{queue.specialist_id}"
        
        # Подсчитываем записи в очереди
        entries_count = db.query(OnlineQueueEntry).filter(
            OnlineQueueEntry.queue_id == queue.id
        ).count()
        
        return QueueCabinetResponse(
            id=queue.id,
            day=queue.day.isoformat(),
            specialist_id=queue.specialist_id,
            specialist_name=specialist_name,
            queue_tag=queue.queue_tag,
            cabinet_number=queue.cabinet_number,
            cabinet_floor=queue.cabinet_floor,
            cabinet_building=queue.cabinet_building,
            entries_count=entries_count,
            active=queue.active
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения информации о кабинете для очереди {queue_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о кабинете: {str(e)}"
        )


# ===================== ОБНОВЛЕНИЕ ИНФОРМАЦИИ О КАБИНЕТАХ =====================

@router.put("/queues/{queue_id}/cabinet-info")
def update_queue_cabinet_info(
    queue_id: int,
    cabinet_info: CabinetInfo,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Обновить информацию о кабинете для очереди
    Доступно только администраторам и регистраторам
    """
    try:
        queue = db.query(DailyQueue).filter(DailyQueue.id == queue_id).first()
        
        if not queue:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Очередь не найдена"
            )
        
        # Обновляем информацию о кабинете
        updated = False
        
        if cabinet_info.cabinet_number is not None:
            queue.cabinet_number = cabinet_info.cabinet_number
            updated = True
        
        if cabinet_info.cabinet_floor is not None:
            queue.cabinet_floor = cabinet_info.cabinet_floor
            updated = True
        
        if cabinet_info.cabinet_building is not None:
            queue.cabinet_building = cabinet_info.cabinet_building
            updated = True
        
        if updated:
            db.commit()
            db.refresh(queue)
        
        return {
            "success": True,
            "message": "Информация о кабинете обновлена",
            "queue_id": queue_id,
            "cabinet_info": {
                "cabinet_number": queue.cabinet_number,
                "cabinet_floor": queue.cabinet_floor,
                "cabinet_building": queue.cabinet_building
            },
            "updated_by": current_user.username,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка обновления информации о кабинете для очереди {queue_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления информации о кабинете: {str(e)}"
        )


@router.put("/queues/cabinet-info/bulk")
def bulk_update_cabinet_info(
    request: BulkCabinetUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Массовое обновление информации о кабинетах для нескольких очередей
    """
    try:
        updated_queues = []
        errors = []
        
        for update in request.updates:
            try:
                queue = db.query(DailyQueue).filter(DailyQueue.id == update.queue_id).first()
                
                if not queue:
                    errors.append({
                        "queue_id": update.queue_id,
                        "error": "Очередь не найдена"
                    })
                    continue
                
                # Обновляем информацию о кабинете
                updated = False
                
                if update.cabinet_info.cabinet_number is not None:
                    queue.cabinet_number = update.cabinet_info.cabinet_number
                    updated = True
                
                if update.cabinet_info.cabinet_floor is not None:
                    queue.cabinet_floor = update.cabinet_info.cabinet_floor
                    updated = True
                
                if update.cabinet_info.cabinet_building is not None:
                    queue.cabinet_building = update.cabinet_info.cabinet_building
                    updated = True
                
                if updated:
                    updated_queues.append({
                        "queue_id": update.queue_id,
                        "cabinet_info": {
                            "cabinet_number": queue.cabinet_number,
                            "cabinet_floor": queue.cabinet_floor,
                            "cabinet_building": queue.cabinet_building
                        }
                    })
                
            except Exception as e:
                errors.append({
                    "queue_id": update.queue_id,
                    "error": str(e)
                })
        
        # Сохраняем изменения
        if updated_queues:
            db.commit()
        
        return {
            "success": True,
            "message": f"Обновлено {len(updated_queues)} очередей",
            "updated_queues": updated_queues,
            "errors": errors,
            "updated_by": current_user.username,
            "updated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка массового обновления информации о кабинетах: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка массового обновления: {str(e)}"
        )


# ===================== СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ DOCTORS =====================

@router.post("/queues/sync-cabinet-info")
def sync_cabinet_info_from_doctors(
    day: Optional[str] = Query(None, description="Дата для синхронизации (по умолчанию сегодня)"),
    specialist_id: Optional[int] = Query(None, description="ID конкретного специалиста"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin"))
):
    """
    Синхронизировать информацию о кабинетах из таблицы doctors
    Доступно только администраторам
    """
    try:
        # Определяем дату
        if day:
            try:
                day_obj = datetime.strptime(day, "%Y-%m-%d").date()
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты. Используйте YYYY-MM-DD"
                )
        else:
            day_obj = date.today()
        
        # Строим запрос для очередей
        query = db.query(DailyQueue).filter(DailyQueue.day == day_obj)
        
        if specialist_id:
            query = query.filter(DailyQueue.specialist_id == specialist_id)
        
        queues = query.all()
        
        updated_count = 0
        errors = []
        
        for queue in queues:
            try:
                # Получаем информацию о враче
                doctor = db.query(Doctor).filter(Doctor.id == queue.specialist_id).first()
                
                if doctor and doctor.cabinet and queue.cabinet_number != doctor.cabinet:
                    queue.cabinet_number = doctor.cabinet
                    updated_count += 1
                
            except Exception as e:
                errors.append({
                    "queue_id": queue.id,
                    "specialist_id": queue.specialist_id,
                    "error": str(e)
                })
        
        # Сохраняем изменения
        if updated_count > 0:
            db.commit()
        
        return {
            "success": True,
            "message": f"Синхронизировано {updated_count} очередей",
            "updated_count": updated_count,
            "total_queues": len(queues),
            "errors": errors,
            "sync_date": day_obj.isoformat(),
            "synced_by": current_user.username,
            "synced_at": datetime.utcnow().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Ошибка синхронизации информации о кабинетах: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}"
        )


# ===================== СТАТИСТИКА ПО КАБИНЕТАМ =====================

@router.get("/queues/cabinet-statistics")
def get_cabinet_statistics(
    date_from: Optional[str] = Query(None, description="Дата начала в формате YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, description="Дата окончания в формате YYYY-MM-DD"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar"))
):
    """
    Получить статистику использования кабинетов
    """
    try:
        # Строим запрос
        query = db.query(DailyQueue)
        
        # Фильтры по датам
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                query = query.filter(DailyQueue.day >= date_from_obj)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты начала. Используйте YYYY-MM-DD"
                )
        
        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                query = query.filter(DailyQueue.day <= date_to_obj)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Неверный формат даты окончания. Используйте YYYY-MM-DD"
                )
        
        queues = query.all()
        
        # Собираем статистику
        cabinet_stats = {}
        total_queues = len(queues)
        queues_with_cabinet = 0
        
        for queue in queues:
            if queue.cabinet_number:
                queues_with_cabinet += 1
                
                if queue.cabinet_number not in cabinet_stats:
                    cabinet_stats[queue.cabinet_number] = {
                        "cabinet_number": queue.cabinet_number,
                        "cabinet_floor": queue.cabinet_floor,
                        "cabinet_building": queue.cabinet_building,
                        "queue_count": 0,
                        "total_entries": 0,
                        "specialists": set()
                    }
                
                cabinet_stats[queue.cabinet_number]["queue_count"] += 1
                cabinet_stats[queue.cabinet_number]["specialists"].add(queue.specialist_id)
                
                # Подсчитываем записи
                entries_count = db.query(OnlineQueueEntry).filter(
                    OnlineQueueEntry.queue_id == queue.id
                ).count()
                cabinet_stats[queue.cabinet_number]["total_entries"] += entries_count
        
        # Преобразуем в список и убираем set
        cabinet_list = []
        for cabinet_number, stats in cabinet_stats.items():
            stats["specialists_count"] = len(stats["specialists"])
            del stats["specialists"]  # Удаляем set, так как он не сериализуется в JSON
            cabinet_list.append(stats)
        
        # Сортируем по количеству очередей
        cabinet_list.sort(key=lambda x: x["queue_count"], reverse=True)
        
        return {
            "success": True,
            "statistics": {
                "total_queues": total_queues,
                "queues_with_cabinet": queues_with_cabinet,
                "queues_without_cabinet": total_queues - queues_with_cabinet,
                "cabinet_coverage": round((queues_with_cabinet / total_queues * 100) if total_queues > 0 else 0, 2),
                "unique_cabinets": len(cabinet_stats),
                "cabinets": cabinet_list
            },
            "period": {
                "date_from": date_from,
                "date_to": date_to
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения статистики по кабинетам: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}"
        )


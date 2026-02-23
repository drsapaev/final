"""
API endpoints для управления информацией о кабинетах в очередях
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.queue_cabinet_management_api_service import (
    QueueCabinetManagementApiService,
    QueueCabinetManagementDomainError,
)

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
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить информацию о кабинетах для очередей
    """
    try:
        payload = QueueCabinetManagementApiService(db).get_queues_cabinet_info(
            day=day,
            specialist_id=specialist_id,
            cabinet_number=cabinet_number,
        )
        return [QueueCabinetResponse(**item) for item in payload]
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        logger.error(f"Ошибка получения информации о кабинетах: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о кабинетах: {str(e)}",
        )


@router.get("/queues/{queue_id}/cabinet-info")
def get_queue_cabinet_info(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить информацию о кабинете для конкретной очереди
    """
    try:
        payload = QueueCabinetManagementApiService(db).get_queue_cabinet_info(queue_id=queue_id)
        return QueueCabinetResponse(**payload)
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        logger.error(
            f"Ошибка получения информации о кабинете для очереди {queue_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения информации о кабинете: {str(e)}",
        )


# ===================== ОБНОВЛЕНИЕ ИНФОРМАЦИИ О КАБИНЕТАХ =====================


@router.put("/queues/{queue_id}/cabinet-info")
def update_queue_cabinet_info(
    queue_id: int,
    cabinet_info: CabinetInfo,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Обновить информацию о кабинете для очереди
    Доступно только администраторам и регистраторам
    """
    service = QueueCabinetManagementApiService(db)
    try:
        return service.update_queue_cabinet_info(
            queue_id=queue_id,
            cabinet_info=cabinet_info.model_dump() if hasattr(cabinet_info, "model_dump") else cabinet_info.dict(),
            updated_by=current_user.username,
        )
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        logger.error(
            f"Ошибка обновления информации о кабинете для очереди {queue_id}: {e}"
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления информации о кабинете: {str(e)}",
        )


@router.put("/queues/cabinet-info/bulk")
def bulk_update_cabinet_info(
    request: BulkCabinetUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Массовое обновление информации о кабинетах для нескольких очередей
    """
    service = QueueCabinetManagementApiService(db)
    try:
        updates = request.model_dump()["updates"] if hasattr(request, "model_dump") else request.dict()["updates"]
        return service.bulk_update_cabinet_info(
            updates=updates,
            updated_by=current_user.username,
        )
    except Exception as e:
        service.rollback()
        logger.error(f"Ошибка массового обновления информации о кабинетах: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка массового обновления: {str(e)}",
        )


# ===================== СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ DOCTORS =====================


@router.post("/queues/sync-cabinet-info")
def sync_cabinet_info_from_doctors(
    day: Optional[str] = Query(
        None, description="Дата для синхронизации (по умолчанию сегодня)"
    ),
    specialist_id: Optional[int] = Query(
        None, description="ID конкретного специалиста"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Синхронизировать информацию о кабинетах из таблицы doctors
    Доступно только администраторам
    """
    service = QueueCabinetManagementApiService(db)
    try:
        return service.sync_cabinet_info_from_doctors(
            day=day,
            specialist_id=specialist_id,
            synced_by=current_user.username,
        )
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        service.rollback()
        logger.error(f"Ошибка синхронизации информации о кабинетах: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка синхронизации: {str(e)}",
        )


# ===================== СТАТИСТИКА ПО КАБИНЕТАМ =====================


@router.get("/queues/cabinet-statistics")
def get_cabinet_statistics(
    date_from: Optional[str] = Query(
        None, description="Дата начала в формате YYYY-MM-DD"
    ),
    date_to: Optional[str] = Query(
        None, description="Дата окончания в формате YYYY-MM-DD"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить статистику использования кабинетов
    """
    try:
        return QueueCabinetManagementApiService(db).get_cabinet_statistics(
            date_from=date_from,
            date_to=date_to,
        )
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        logger.error(f"Ошибка получения статистики по кабинетам: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статистики: {str(e)}",
        )

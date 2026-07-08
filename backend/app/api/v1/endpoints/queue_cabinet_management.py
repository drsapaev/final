"""
API endpoints для управления информацией о кабинетах в очередях
"""

import logging
from datetime import date, datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.queue_cabinet_management_api_service import (
    QueueCabinetManagementApiService,
    QueueCabinetManagementDomainError,
)
from app.services.queue_domain_service import QueueDomainReadError, QueueDomainService

logger = logging.getLogger(__name__)

router = APIRouter()


def _raise_queue_cabinet_internal_error(action: str, exc: Exception) -> NoReturn:
    logger.error(
        "Queue cabinet management endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


def _parse_day_query(day: str | None) -> date | None:
    if day is None:
        return None
    try:
        return datetime.strptime(day, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Неверный формат даты. Используйте YYYY-MM-DD",
        ) from exc


# ===================== МОДЕЛИ ДАННЫХ =====================


class CabinetInfo(BaseModel):
    cabinet_number: str | None = None
    cabinet_floor: int | None = None
    cabinet_building: str | None = None


class QueueCabinetUpdateRequest(BaseModel):
    queue_id: int
    cabinet_info: CabinetInfo


class QueueCabinetResponse(BaseModel):
    id: int
    day: str
    specialist_id: int
    specialist_name: str
    queue_tag: str | None
    cabinet_number: str | None
    doctor_cabinet: str | None
    effective_cabinet: str | None
    cabinet_floor: int | None
    cabinet_building: str | None
    entries_count: int
    active: bool
    linked_doctor_found: bool
    doctor_has_cabinet: bool
    sync_status: str
    integrity_warnings: list[str]


class BulkCabinetUpdateRequest(BaseModel):
    updates: list[QueueCabinetUpdateRequest]


# ===================== ПОЛУЧЕНИЕ ИНФОРМАЦИИ О КАБИНЕТАХ =====================


@router.get("/queues/cabinet-info", response_model=list[QueueCabinetResponse])
def get_queues_cabinet_info(
    day: str | None = Query(None, description="Дата в формате YYYY-MM-DD"),
    specialist_id: int | None = Query(None, description="ID специалиста"),
    cabinet_number: str | None = Query(None, description="Номер кабинета"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить информацию о кабинетах для очередей
    """
    try:
        payload = QueueDomainService(db).list_queue_cabinet_info(
            day=_parse_day_query(day),
            specialist_id=specialist_id,
            cabinet_number=cabinet_number,
        )
        return [QueueCabinetResponse(**item) for item in payload]
    except QueueDomainReadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_cabinet_internal_error("get_queues_cabinet_info", exc)


@router.get("/queues/{queue_id}/cabinet-info", response_model=dict[str, Any])
def get_queue_cabinet_info(
    queue_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar", "Doctor")),
):
    """
    Получить информацию о кабинете для конкретной очереди
    """
    try:
        payload = QueueDomainService(db).get_queue_cabinet_info(queue_id=queue_id)
        return QueueCabinetResponse(**payload)
    except QueueDomainReadError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_cabinet_internal_error("get_queue_cabinet_info", exc)


# ===================== ОБНОВЛЕНИЕ ИНФОРМАЦИИ О КАБИНЕТАХ =====================


@router.put("/queues/{queue_id}/cabinet-info", response_model=dict[str, Any])
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
            cabinet_info=(
                cabinet_info.model_dump(exclude_unset=True)
                if hasattr(cabinet_info, "model_dump")
                else cabinet_info.dict(exclude_unset=True)
            ),
            updated_by=current_user.username,
        )
    except QueueCabinetManagementDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except HTTPException:
        raise
    except Exception as exc:
        service.rollback()
        _raise_queue_cabinet_internal_error("update_queue_cabinet_info", exc)


@router.put("/queues/cabinet-info/bulk", response_model=dict[str, Any])
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
        updates = (
            request.model_dump(exclude_unset=True)["updates"]
            if hasattr(request, "model_dump")
            else request.dict(exclude_unset=True)["updates"]
        )
        return service.bulk_update_cabinet_info(
            updates=updates,
            updated_by=current_user.username,
        )
    except HTTPException:
        raise
    except Exception as exc:
        service.rollback()
        _raise_queue_cabinet_internal_error("bulk_update_cabinet_info", exc)


# ===================== СИНХРОНИЗАЦИЯ С ТАБЛИЦЕЙ DOCTORS =====================


@router.post("/queues/sync-cabinet-info", response_model=dict[str, Any])
def sync_cabinet_info_from_doctors(
    day: str | None = Query(
        None, description="Дата для синхронизации (по умолчанию сегодня)"
    ),
    specialist_id: int | None = Query(None, description="ID конкретного специалиста"),
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
    except HTTPException:
        raise
    except Exception as exc:
        service.rollback()
        _raise_queue_cabinet_internal_error("sync_cabinet_info_from_doctors", exc)


# ===================== СТАТИСТИКА ПО КАБИНЕТАМ =====================


@router.get("/queues/cabinet-statistics", response_model=dict[str, Any])
def get_cabinet_statistics(
    date_from: str | None = Query(None, description="Дата начала в формате YYYY-MM-DD"),
    date_to: str | None = Query(
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
    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_cabinet_internal_error("get_cabinet_statistics", exc)

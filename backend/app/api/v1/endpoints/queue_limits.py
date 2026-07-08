"""
API для управления лимитами онлайн-очередей
"""

import logging
from datetime import date, datetime
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.queue_domain_service import QueueDomainService
from app.services.queue_limits_api_service import QueueLimitsApiService

logger = logging.getLogger(__name__)

router = APIRouter()


def _raise_queue_limits_internal_error(action: str, exc: Exception) -> NoReturn:
    logger.error(
        "Queue limits endpoint failed action=%s error_type=%s",
        action,
        type(exc).__name__,
    )
    raise HTTPException(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        detail="Internal server error",
    ) from exc


# ===================== PYDANTIC МОДЕЛИ =====================


class QueueLimitSettings(BaseModel):
    """Настройки лимитов для специальности"""

    specialty: str = Field(..., description="Специальность врача")
    max_per_day: int = Field(15, ge=1, le=100, description="Максимум записей в день")
    start_number: int = Field(1, ge=1, le=999, description="Начальный номер очереди")
    enabled: bool = Field(True, description="Включены ли лимиты для этой специальности")


class QueueLimitUpdate(BaseModel):
    """Обновление лимитов"""

    specialty: str = Field(..., description="Специальность")
    max_per_day: int | None = Field(None, ge=1, le=100)
    start_number: int | None = Field(None, ge=1, le=999)
    enabled: bool | None = Field(None)


class DoctorQueueLimit(BaseModel):
    """Индивидуальный лимит для врача"""

    doctor_id: int = Field(..., description="ID врача")
    day: date = Field(..., description="Дата")
    max_online_entries: int = Field(
        15, ge=0, le=100, description="Максимум онлайн записей"
    )


class QueueLimitResponse(BaseModel):
    """Ответ с информацией о лимитах"""

    specialty: str
    max_per_day: int
    start_number: int
    enabled: bool
    current_usage: int
    doctors_count: int
    last_updated: datetime | None


class QueueStatusResponse(BaseModel):
    """Статус очереди с лимитами"""

    doctor_id: int
    doctor_name: str
    specialty: str
    cabinet: str | None
    day: date
    current_entries: int
    max_entries: int
    limit_reached: bool
    queue_opened: bool
    online_available: bool


# ===================== ПОЛУЧЕНИЕ НАСТРОЕК ЛИМИТОВ =====================


@router.get("/queue-limits", response_model=list[QueueLimitResponse])
def get_queue_limits(
    specialty: str | None = Query(None, description="Фильтр по специальности"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить настройки лимитов очередей
    """
    try:
        result = QueueLimitsApiService(db).get_queue_limits(specialty=specialty)
        return [QueueLimitResponse(**item) for item in result]

    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_limits_internal_error("get_queue_limits", exc)


# ===================== ОБНОВЛЕНИЕ ЛИМИТОВ =====================


@router.put("/queue-limits", response_model=dict[str, Any])
def update_queue_limits(
    limits: list[QueueLimitUpdate],
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Обновить настройки лимитов очередей
    """
    try:
        return QueueLimitsApiService(db).update_queue_limits(
            limits=limits,
            current_user_id=current_user.id,
        )

    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_limits_internal_error("update_queue_limits", exc)


# ===================== СТАТУС ОЧЕРЕДЕЙ С ЛИМИТАМИ =====================


@router.get("/queue-status", response_model=list[QueueStatusResponse])
def get_queue_status_with_limits(
    day: date | None = Query(None, description="Дата (по умолчанию сегодня)"),
    specialty: str | None = Query(None, description="Фильтр по специальности"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить статус очередей с информацией о лимитах
    """
    try:
        if day is None:
            day = date.today()

        result = QueueDomainService(db).get_queue_limits_status(
            day=day,
            specialty=specialty,
        )
        return [QueueStatusResponse(**item) for item in result]

    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_limits_internal_error("get_queue_status_with_limits", exc)


# ===================== ИНДИВИДУАЛЬНЫЕ ЛИМИТЫ ДЛЯ ВРАЧЕЙ =====================


@router.put("/doctor-queue-limit", response_model=dict[str, Any])
def set_doctor_queue_limit(
    limit_data: DoctorQueueLimit,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Установить индивидуальный лимит для врача на конкретный день
    """
    try:
        return QueueLimitsApiService(db).set_doctor_queue_limit(limit_data=limit_data)
    except ValueError as exc:
        if exc.args and exc.args[0] == "DOCTOR_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден",
            ) from exc
        raise
    except HTTPException:
        raise
    except Exception as exc:
        QueueLimitsApiService(db).rollback()
        _raise_queue_limits_internal_error("set_doctor_queue_limit", exc)


# ===================== СБРОС ЛИМИТОВ =====================


@router.post("/reset-queue-limits", response_model=dict[str, Any])
def reset_queue_limits(
    specialty: str | None = Query(
        None, description="Сбросить лимиты для конкретной специальности"
    ),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin")),
):
    """
    Сбросить лимиты очередей к значениям по умолчанию
    """
    try:
        return QueueLimitsApiService(db).reset_queue_limits(
            specialty=specialty,
            current_user_id=current_user.id,
        )

    except HTTPException:
        raise
    except Exception as exc:
        _raise_queue_limits_internal_error("reset_queue_limits", exc)

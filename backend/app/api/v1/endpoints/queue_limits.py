"""
API для управления лимитами онлайн-очередей
"""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.user import User
from app.services.queue_limits_api_service import QueueLimitsApiService

router = APIRouter()


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
    max_per_day: Optional[int] = Field(None, ge=1, le=100)
    start_number: Optional[int] = Field(None, ge=1, le=999)
    enabled: Optional[bool] = Field(None)


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
    last_updated: Optional[datetime]


class QueueStatusResponse(BaseModel):
    """Статус очереди с лимитами"""

    doctor_id: int
    doctor_name: str
    specialty: str
    cabinet: Optional[str]
    day: date
    current_entries: int
    max_entries: int
    limit_reached: bool
    queue_opened: bool
    online_available: bool


# ===================== ПОЛУЧЕНИЕ НАСТРОЕК ЛИМИТОВ =====================


@router.get("/queue-limits", response_model=List[QueueLimitResponse])
def get_queue_limits(
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить настройки лимитов очередей
    """
    try:
        result = QueueLimitsApiService(db).get_queue_limits(specialty=specialty)
        return [QueueLimitResponse(**item) for item in result]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения лимитов: {str(e)}",
        ) from e


# ===================== ОБНОВЛЕНИЕ ЛИМИТОВ =====================


@router.put("/queue-limits")
def update_queue_limits(
    limits: List[QueueLimitUpdate],
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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка обновления лимитов: {str(e)}",
        ) from e


# ===================== СТАТУС ОЧЕРЕДЕЙ С ЛИМИТАМИ =====================


@router.get("/queue-status", response_model=List[QueueStatusResponse])
def get_queue_status_with_limits(
    day: Optional[date] = Query(None, description="Дата (по умолчанию сегодня)"),
    specialty: Optional[str] = Query(None, description="Фильтр по специальности"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("Admin", "Registrar")),
):
    """
    Получить статус очередей с информацией о лимитах
    """
    try:
        if day is None:
            day = date.today()

        result = QueueLimitsApiService(db).get_queue_status_with_limits(
            day=day,
            specialty=specialty,
        )
        return [QueueStatusResponse(**item) for item in result]

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка получения статуса очередей: {str(e)}",
        ) from e


# ===================== ИНДИВИДУАЛЬНЫЕ ЛИМИТЫ ДЛЯ ВРАЧЕЙ =====================


@router.put("/doctor-queue-limit")
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
        if str(exc) == "DOCTOR_NOT_FOUND":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Врач не найден",
            ) from exc
        raise
    except HTTPException:
        raise
    except Exception as e:
        QueueLimitsApiService(db).rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка установки лимита: {str(e)}",
        ) from e


# ===================== СБРОС ЛИМИТОВ =====================


@router.post("/reset-queue-limits")
def reset_queue_limits(
    specialty: Optional[str] = Query(
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

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка сброса лимитов: {str(e)}",
        ) from e

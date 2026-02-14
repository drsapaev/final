"""
Salary History API Endpoints
Эндпоинты для управления историей зарплат
"""

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.salary_api_service import SalaryApiDomainError, SalaryApiService

import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/salary", tags=["salary"])


# ===================== СХЕМЫ =====================


class SalaryChangeCreate(BaseModel):
    user_id: int
    new_salary: Decimal
    change_type: str = "adjustment"
    reason: Optional[str] = None
    effective_date: datetime
    currency: str = "UZS"


class SalaryPaymentCreate(BaseModel):
    user_id: int
    period_start: datetime
    period_end: datetime
    base_salary: Decimal
    bonuses: Decimal = Decimal("0")
    deductions: Decimal = Decimal("0")
    taxes: Decimal = Decimal("0")
    currency: str = "UZS"
    notes: Optional[str] = None


def _model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


# ===================== ИСТОРИЯ ЗАРПЛАТ =====================


@router.get("/history/{user_id}", summary="История зарплат сотрудника")
async def get_salary_history(
    user_id: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
    limit: int = Query(50, ge=1, le=200),
) -> List[Dict[str, Any]]:
    """
    Получить историю изменений зарплаты сотрудника
    """
    try:
        return SalaryApiService(db).get_salary_history(user_id=user_id, limit=limit)
    except Exception as e:
        logger.error(f"Error getting salary history: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения истории: {str(e)}")


@router.post("/change", summary="Изменить зарплату")
async def create_salary_change(
    data: SalaryChangeCreate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
) -> Dict[str, Any]:
    """
    Создать запись об изменении зарплаты
    """
    service = SalaryApiService(db)
    try:
        return service.create_salary_change(
            payload=_model_to_dict(data),
            changed_by_id=user.id,
        )
    except Exception as e:
        logger.error(f"Error creating salary change: {e}")
        service.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка записи изменения: {str(e)}")


@router.put("/change/{record_id}/confirm", summary="Подтвердить изменение")
async def confirm_salary_change(
    record_id: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin")),
) -> Dict[str, Any]:
    """
    Подтвердить изменение зарплаты
    """
    service = SalaryApiService(db)
    try:
        return service.confirm_salary_change(record_id=record_id, confirmed_by_id=user.id)
    except SalaryApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        logger.error(f"Error confirming salary change: {e}")
        service.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка подтверждения: {str(e)}")


# ===================== ВЫПЛАТЫ =====================


@router.get("/payments/{user_id}", summary="История выплат")
async def get_salary_payments(
    user_id: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
    year: Optional[int] = None,
    limit: int = Query(24, ge=1, le=100),
) -> List[Dict[str, Any]]:
    """
    Получить историю выплат зарплаты сотрудника
    """
    try:
        return SalaryApiService(db).get_salary_payments(
            user_id=user_id,
            year=year,
            limit=limit,
        )
    except Exception as e:
        logger.error(f"Error getting salary payments: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения выплат: {str(e)}")


@router.post("/payment", summary="Создать запись о выплате")
async def create_salary_payment(
    data: SalaryPaymentCreate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
) -> Dict[str, Any]:
    """
    Создать запись о выплате зарплаты
    """
    service = SalaryApiService(db)
    try:
        return service.create_salary_payment(payload=_model_to_dict(data))
    except Exception as e:
        logger.error(f"Error creating salary payment: {e}")
        service.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка создания выплаты: {str(e)}")


@router.put("/payment/{payment_id}/status", summary="Обновить статус выплаты")
async def update_payment_status(
    payment_id: int,
    status: str,
    payment_date: Optional[datetime] = None,
    payment_method: Optional[str] = None,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin")),
) -> Dict[str, Any]:
    """
    Обновить статус выплаты зарплаты
    """
    service = SalaryApiService(db)
    try:
        return service.update_payment_status(
            payment_id=payment_id,
            new_status=status,
            payment_date=payment_date,
            payment_method=payment_method,
        )
    except SalaryApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as e:
        logger.error(f"Error updating payment status: {e}")
        service.rollback()
        raise HTTPException(status_code=500, detail=f"Ошибка обновления: {str(e)}")


@router.get("/summary/{user_id}", summary="Сводка по зарплате")
async def get_salary_summary(
    user_id: int,
    year: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
) -> Dict[str, Any]:
    """
    Получить годовую сводку по зарплате сотрудника
    """
    try:
        return SalaryApiService(db).get_salary_summary(user_id=user_id, year=year)
    except Exception as e:
        logger.error(f"Error getting salary summary: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения сводки: {str(e)}")

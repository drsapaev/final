"""
Salary History API Endpoints
Эндпоинты для управления историей зарплат
"""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Any, NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api import deps
from app.models.user import User
from app.services.salary_api_service import SalaryApiDomainError, SalaryApiService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/salary", tags=["salary"])

SALARY_PUBLIC_ERROR = "Salary operation failed"


def _raise_salary_internal_error(operation: str, exc: Exception) -> NoReturn:
    logger.warning(
        "Salary endpoint failed operation=%s error_type=%s",
        operation,
        type(exc).__name__,
    )
    raise HTTPException(status_code=500, detail=SALARY_PUBLIC_ERROR) from exc


# ===================== СХЕМЫ =====================


class SalaryChangeCreate(BaseModel):
    user_id: int
    new_salary: Decimal
    change_type: str = "adjustment"
    reason: str | None = None
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
    notes: str | None = None


def _model_to_dict(model: BaseModel) -> dict:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


# ===================== ИСТОРИЯ ЗАРПЛАТ =====================


@router.get("/history/{user_id}", summary="История зарплат сотрудника", response_model=list[dict[str, Any]])
async def get_salary_history(
    user_id: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict[str, Any]]:
    """
    Получить историю изменений зарплаты сотрудника
    """
    try:
        return SalaryApiService(db).get_salary_history(user_id=user_id, limit=limit)
    except Exception as exc:
        _raise_salary_internal_error("get_salary_history", exc)


@router.post("/change", summary="Изменить зарплату", response_model=dict[str, Any])
async def create_salary_change(
    data: SalaryChangeCreate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
) -> dict[str, Any]:
    """
    Создать запись об изменении зарплаты
    """
    service = SalaryApiService(db)
    try:
        return service.create_salary_change(
            payload=_model_to_dict(data),
            changed_by_id=user.id,
        )
    except Exception as exc:
        service.rollback()
        _raise_salary_internal_error("create_salary_change", exc)


@router.put("/change/{record_id}/confirm", summary="Подтвердить изменение", response_model=dict[str, Any])
async def confirm_salary_change(
    record_id: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin")),
) -> dict[str, Any]:
    """
    Подтвердить изменение зарплаты
    """
    service = SalaryApiService(db)
    try:
        return service.confirm_salary_change(record_id=record_id, confirmed_by_id=user.id)
    except SalaryApiDomainError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except Exception as exc:
        service.rollback()
        _raise_salary_internal_error("confirm_salary_change", exc)


# ===================== ВЫПЛАТЫ =====================


@router.get("/payments/{user_id}", summary="История выплат", response_model=list[dict[str, Any]])
async def get_salary_payments(
    user_id: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
    year: int | None = None,
    limit: int = Query(24, ge=1, le=100),
) -> list[dict[str, Any]]:
    """
    Получить историю выплат зарплаты сотрудника
    """
    try:
        return SalaryApiService(db).get_salary_payments(
            user_id=user_id,
            year=year,
            limit=limit,
        )
    except Exception as exc:
        _raise_salary_internal_error("get_salary_payments", exc)


@router.post("/payment", summary="Создать запись о выплате", response_model=dict[str, Any])
async def create_salary_payment(
    data: SalaryPaymentCreate,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
) -> dict[str, Any]:
    """
    Создать запись о выплате зарплаты
    """
    service = SalaryApiService(db)
    try:
        return service.create_salary_payment(payload=_model_to_dict(data))
    except Exception as exc:
        service.rollback()
        _raise_salary_internal_error("create_salary_payment", exc)


@router.put("/payment/{payment_id}/status", summary="Обновить статус выплаты", response_model=dict[str, Any])
async def update_payment_status(
    payment_id: int,
    status: str,
    payment_date: datetime | None = None,
    payment_method: str | None = None,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin")),
) -> dict[str, Any]:
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
    except Exception as exc:
        service.rollback()
        _raise_salary_internal_error("update_payment_status", exc)


@router.get("/summary/{user_id}", summary="Сводка по зарплате", response_model=dict[str, Any])
async def get_salary_summary(
    user_id: int,
    year: int,
    db: Session = Depends(deps.get_db),
    user: User = Depends(deps.require_roles("Admin", "HR")),
) -> dict[str, Any]:
    """
    Получить годовую сводку по зарплате сотрудника
    """
    try:
        return SalaryApiService(db).get_salary_summary(user_id=user_id, year=year)
    except Exception as exc:
        _raise_salary_internal_error("get_salary_summary", exc)

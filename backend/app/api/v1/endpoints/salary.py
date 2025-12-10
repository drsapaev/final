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
from sqlalchemy import desc

from app.api import deps
from app.models.user import User
from app.models.salary_history import SalaryHistory, SalaryPayment
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
        history = (
            db.query(SalaryHistory)
            .filter(SalaryHistory.user_id == user_id)
            .order_by(desc(SalaryHistory.effective_date))
            .limit(limit)
            .all()
        )
        
        return [
            {
                "id": h.id,
                "old_salary": float(h.old_salary) if h.old_salary else None,
                "new_salary": float(h.new_salary),
                "currency": h.currency,
                "change_type": h.change_type,
                "change_amount": float(h.change_amount),
                "change_percentage": float(h.change_percentage) if h.change_percentage else None,
                "is_increase": h.is_increase,
                "reason": h.reason,
                "effective_date": h.effective_date.isoformat(),
                "is_confirmed": h.is_confirmed,
                "created_at": h.created_at.isoformat(),
            }
            for h in history
        ]
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
    try:
        # Получаем текущую зарплату
        last_record = (
            db.query(SalaryHistory)
            .filter(SalaryHistory.user_id == data.user_id)
            .order_by(desc(SalaryHistory.effective_date))
            .first()
        )
        
        old_salary = last_record.new_salary if last_record else None
        
        # Вычисляем процент изменения
        change_percentage = None
        if old_salary and old_salary > 0:
            change_percentage = ((data.new_salary - old_salary) / old_salary) * 100
        
        record = SalaryHistory(
            user_id=data.user_id,
            old_salary=old_salary,
            new_salary=data.new_salary,
            currency=data.currency,
            change_type=data.change_type,
            change_percentage=change_percentage,
            reason=data.reason,
            effective_date=data.effective_date,
            changed_by_id=user.id,
            created_at=datetime.utcnow(),
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        
        return {
            "success": True,
            "id": record.id,
            "message": "Изменение зарплаты записано",
            "change_percentage": float(change_percentage) if change_percentage else None,
        }
    except Exception as e:
        logger.error(f"Error creating salary change: {e}")
        db.rollback()
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
    try:
        record = db.query(SalaryHistory).filter(SalaryHistory.id == record_id).first()
        
        if not record:
            raise HTTPException(status_code=404, detail="Запись не найдена")
        
        record.is_confirmed = True
        record.confirmed_at = datetime.utcnow()
        record.confirmed_by_id = user.id
        
        db.commit()
        
        return {"success": True, "message": "Изменение подтверждено"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming salary change: {e}")
        db.rollback()
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
        query = db.query(SalaryPayment).filter(SalaryPayment.user_id == user_id)
        
        if year:
            query = query.filter(
                SalaryPayment.period_start >= datetime(year, 1, 1),
                SalaryPayment.period_end <= datetime(year, 12, 31, 23, 59, 59),
            )
        
        payments = query.order_by(desc(SalaryPayment.period_end)).limit(limit).all()
        
        return [
            {
                "id": p.id,
                "period_start": p.period_start.isoformat(),
                "period_end": p.period_end.isoformat(),
                "base_salary": float(p.base_salary),
                "bonuses": float(p.bonuses),
                "deductions": float(p.deductions),
                "taxes": float(p.taxes),
                "net_amount": float(p.net_amount),
                "currency": p.currency,
                "status": p.status,
                "payment_date": p.payment_date.isoformat() if p.payment_date else None,
                "payment_method": p.payment_method,
            }
            for p in payments
        ]
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
    try:
        net_amount = data.base_salary + data.bonuses - data.deductions - data.taxes
        
        payment = SalaryPayment(
            user_id=data.user_id,
            period_start=data.period_start,
            period_end=data.period_end,
            base_salary=data.base_salary,
            bonuses=data.bonuses,
            deductions=data.deductions,
            taxes=data.taxes,
            net_amount=net_amount,
            currency=data.currency,
            notes=data.notes,
            status="pending",
            created_at=datetime.utcnow(),
        )
        
        db.add(payment)
        db.commit()
        db.refresh(payment)
        
        return {
            "success": True,
            "id": payment.id,
            "net_amount": float(net_amount),
        }
    except Exception as e:
        logger.error(f"Error creating salary payment: {e}")
        db.rollback()
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
    try:
        payment = db.query(SalaryPayment).filter(SalaryPayment.id == payment_id).first()
        
        if not payment:
            raise HTTPException(status_code=404, detail="Выплата не найдена")
        
        valid_statuses = ["pending", "approved", "paid", "cancelled"]
        if status not in valid_statuses:
            raise HTTPException(status_code=400, detail=f"Неверный статус: {status}")
        
        payment.status = status
        if status == "paid":
            payment.payment_date = payment_date or datetime.utcnow()
            payment.payment_method = payment_method
        
        db.commit()
        
        return {"success": True, "message": f"Статус обновлён на {status}"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating payment status: {e}")
        db.rollback()
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
        payments = (
            db.query(SalaryPayment)
            .filter(
                SalaryPayment.user_id == user_id,
                SalaryPayment.period_start >= datetime(year, 1, 1),
                SalaryPayment.period_end <= datetime(year, 12, 31, 23, 59, 59),
            )
            .all()
        )
        
        total_base = sum(float(p.base_salary) for p in payments)
        total_bonuses = sum(float(p.bonuses) for p in payments)
        total_deductions = sum(float(p.deductions) for p in payments)
        total_taxes = sum(float(p.taxes) for p in payments)
        total_net = sum(float(p.net_amount) for p in payments)
        
        return {
            "user_id": user_id,
            "year": year,
            "payments_count": len(payments),
            "total_base_salary": total_base,
            "total_bonuses": total_bonuses,
            "total_deductions": total_deductions,
            "total_taxes": total_taxes,
            "total_net_amount": total_net,
            "average_monthly": total_net / 12 if payments else 0,
        }
    except Exception as e:
        logger.error(f"Error getting salary summary: {e}")
        raise HTTPException(status_code=500, detail=f"Ошибка получения сводки: {str(e)}")

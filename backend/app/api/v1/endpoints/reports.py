from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.payment import Payment

router = APIRouter(prefix="/reports", tags=["reports"], dependencies=[Depends(require_roles("Admin"))])


@router.get("/summary", summary="Сводка доходов за период")
def summary(
    date_from: date = Query(..., alias="from"),
    date_to: date = Query(..., alias="to"),
    db: Session = Depends(get_db),
):
    if date_from > date_to:
        raise HTTPException(status_code=422, detail="from must be <= to")

    dt_from = datetime.combine(date_from, datetime.min.time())
    dt_to = datetime.combine(date_to, datetime.max.time())

    # Общая сумма оплаченных платежей
    stmt_total = (
        select(func.coalesce(func.sum(Payment.amount), 0))
        .where(Payment.status == "paid")
        .where(Payment.created_at >= dt_from, Payment.created_at <= dt_to)
    )
    total = float(db.execute(stmt_total).scalar_one() or 0)

    # По дням
    stmt_by_day = (
        select(func.date(Payment.created_at).label("d"), func.coalesce(func.sum(Payment.amount), 0).label("sum"))
        .where(Payment.status == "paid")
        .where(Payment.created_at >= dt_from, Payment.created_at <= dt_to)
        .group_by(func.date(Payment.created_at))
        .order_by(func.date(Payment.created_at))
    )
    rows = db.execute(stmt_by_day).all()
    by_day = [{"date": str(r.d), "amount": float(r.sum)} for r in rows]

    return {
        "from": str(date_from),
        "to": str(date_to),
        "currency": "UZS",
        "total_paid": total,
        "by_day": by_day,
    }



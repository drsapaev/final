from __future__ import annotations

from typing import Iterable, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.payment import Payment  # type: ignore[attr-defined]


def list_payments(
    db: Session,
    *,
    visit_id: Optional[int] = None,
    limit: int = 200,
    offset: int = 0,
) -> List[Payment]:
    stmt = select(Payment)
    if visit_id:
        stmt = stmt.where(Payment.visit_id == visit_id)
    stmt = stmt.order_by(Payment.id.desc()).limit(limit).offset(offset)
    return list(db.execute(stmt).scalars().all())


def create_payment(
    db: Session,
    *,
    visit_id: int,
    amount: float,
    currency: str = "UZS",
    method: str = "cash",
    status: str = "paid",
    receipt_no: Optional[str] = None,
    note: Optional[str] = None,
) -> Payment:
    row = Payment(
        visit_id=visit_id,
        amount=amount,
        currency=currency,
        method=method,
        status=status,
        receipt_no=receipt_no,
        note=note,
    )
    db.add(row)
    db.flush()
    return row


def sum_paid_by_visit(db: Session, *, visit_id: int) -> float:
    q = select(func.coalesce(func.sum(Payment.amount), 0)).where(
        Payment.visit_id == visit_id, Payment.status == "paid"
    )
    return float(db.execute(q).scalar_one() or 0.0)
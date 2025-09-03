from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_roles
from app.models.payment import Payment  # type: ignore[attr-defined]

router = APIRouter(prefix="/payments", tags=["payments"])


class PaymentOut(BaseModel):
    id: int
    visit_id: Optional[int] = None
    amount: float = 0.0
    method: Optional[str] = None
    created_at: Optional[str] = None


class PaymentCreateIn(BaseModel):
    visit_id: int = Field(ge=1)
    amount: float = Field(ge=0.0)
    method: Optional[str] = Field(default=None, max_length=32)


def _to_out(row: Payment) -> PaymentOut:
    return PaymentOut(
        id=row.id,
        visit_id=getattr(row, "visit_id", None),
        amount=float(getattr(row, "amount", 0.0) or 0.0),
        method=getattr(row, "method", None),
        created_at=str(getattr(row, "created_at", None) or ""),
    )


@router.get("", response_model=List[PaymentOut], summary="Список платежей")
async def list_payments(
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Cashier")),
    visit_id: Optional[int] = Query(default=None, ge=1),
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    stmt = select(Payment)
    if visit_id:
        stmt = stmt.where(Payment.visit_id == visit_id)
    stmt = stmt.order_by(Payment.id.desc()).limit(limit).offset(offset)
    rows = db.execute(stmt).scalars().all()
    return [_to_out(r) for r in rows]


@router.post(
    "",
    response_model=PaymentOut,
    status_code=status.HTTP_201_CREATED,
    summary="Создать платёж",
)
async def create_payment(
    payload: PaymentCreateIn,
    db: Session = Depends(get_db),
    user=Depends(require_roles("Admin", "Cashier")),
):
    row = Payment(
        visit_id=payload.visit_id,
        amount=payload.amount,
        method=(payload.method or "cash"),
    )
    db.add(row)
    db.flush()
    db.refresh(row)
    db.commit()
    return _to_out(row)

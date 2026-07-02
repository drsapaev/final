from __future__ import annotations

from pydantic import Field

from app.schemas.base import ORMModel


class PaymentIn(ORMModel):
    visit_id: int = Field(ge=1)
    amount: float = Field(ge=0)
    currency: str = Field(default="UZS", max_length=8)
    method: str = Field(default="cash", max_length=32)
    status: str = Field(default="paid", max_length=16)
    receipt_no: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=500)


class PaymentOut(ORMModel):
    id: int
    visit_id: int
    amount: float
    currency: str
    method: str
    status: str
    receipt_no: str | None = None
    note: str | None = None

from __future__ import annotations
from app.schemas.base import ORMModel
from typing import Optional

from pydantic import Field


class PaymentIn(ORMModel):
    visit_id: int = Field(ge=1)
    amount: float = Field(ge=0)
    currency: str = Field(default="UZS", max_length=8)
    method: str = Field(default="cash", max_length=32)
    status: str = Field(default="paid", max_length=16)
    receipt_no: Optional[str] = Field(default=None, max_length=64)
    note: Optional[str] = Field(default=None, max_length=500)


class PaymentOut(ORMModel):
    id: int
    visit_id: int
    amount: float
    currency: str
    method: str
    status: str
    receipt_no: Optional[str] = None
    note: Optional[str] = None

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.schemas.base import ORMModel


FinanceTransactionType = Literal["income", "expense"]
FinanceTransactionStatus = Literal["pending", "completed", "cancelled", "refunded"]
FinancePaymentMethod = Literal["cash", "card", "transfer", "mobile"]


class FinanceTransactionBase(BaseModel):
    type: FinanceTransactionType = Field(..., description="Тип операции")
    category: str = Field(..., min_length=1, max_length=255)
    amount: float = Field(..., gt=0, description="Сумма операции")
    description: str = Field(..., min_length=1)
    patient_id: int | None = Field(None, description="ID пациента")
    doctor_id: int | None = Field(None, description="ID врача")
    payment_method: FinancePaymentMethod = Field(default="cash")
    status: FinanceTransactionStatus = Field(default="completed")
    transaction_date: date = Field(..., description="Дата операции")
    notes: str | None = Field(None, max_length=5000)
    reference: str | None = Field(None, max_length=255)

    @field_validator("category", "description", mode="before")
    @classmethod
    def _required_text_fields(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            raise ValueError("Поле обязательно")
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("Поле обязательно")
            return stripped
        return value

    @field_validator("notes", "reference", mode="before")
    @classmethod
    def _optional_text_fields(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value


class FinanceTransactionCreate(FinanceTransactionBase):
    pass


class FinanceTransactionUpdate(BaseModel):
    type: FinanceTransactionType | None = None
    category: str | None = Field(None, min_length=1, max_length=255)
    amount: float | None = Field(None, gt=0)
    description: str | None = Field(None, min_length=1)
    patient_id: int | None = None
    doctor_id: int | None = None
    payment_method: FinancePaymentMethod | None = None
    status: FinanceTransactionStatus | None = None
    transaction_date: date | None = None
    notes: str | None = Field(None, max_length=5000)
    reference: str | None = Field(None, max_length=255)

    @field_validator("category", "description", mode="before")
    @classmethod
    def _required_text_fields(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            if not stripped:
                raise ValueError("Поле обязательно")
            return stripped
        return value

    @field_validator("notes", "reference", mode="before")
    @classmethod
    def _optional_text_fields(cls, value):  # type: ignore[no-untyped-def]
        if value is None:
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value


class FinanceTransactionOut(FinanceTransactionBase, ORMModel):
    id: int
    patient_name: str | None = None
    doctor_name: str | None = None
    created_at: datetime
    updated_at: datetime

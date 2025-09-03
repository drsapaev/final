from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import ORMModel


class AppointmentBase(ORMModel):
    patient_id: int
    doctor_id: Optional[int] = None
    department: Optional[str] = Field(None, max_length=64)
    appointment_date: date
    appointment_time: Optional[str] = Field(None, max_length=8)  # HH:MM
    notes: Optional[str] = Field(None, max_length=1000)
    status: str = Field(
        default="scheduled", max_length=16
    )  # scheduled, confirmed, cancelled, completed

    # Поля для интеграции с платежами
    payment_amount: Optional[float] = None
    payment_currency: Optional[str] = Field(default="UZS", max_length=3)
    payment_provider: Optional[str] = Field(None, max_length=32)
    payment_transaction_id: Optional[str] = Field(None, max_length=128)
    payment_webhook_id: Optional[int] = None
    payment_processed_at: Optional[datetime] = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(ORMModel):
    doctor_id: Optional[int] = None
    department: Optional[str] = Field(None, max_length=64)
    appointment_date: Optional[date] = None
    appointment_time: Optional[str] = Field(None, max_length=8)
    notes: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = Field(None, max_length=16)

    # Поля для интеграции с платежами
    payment_amount: Optional[float] = None
    payment_currency: Optional[str] = Field(None, max_length=3)
    payment_provider: Optional[str] = Field(None, max_length=32)
    payment_transaction_id: Optional[str] = Field(None, max_length=128)
    payment_webhook_id: Optional[int] = None
    payment_processed_at: Optional[datetime] = None


class Appointment(AppointmentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None

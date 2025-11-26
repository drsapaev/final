from __future__ import annotations

from datetime import date, datetime
from typing import List, Optional

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

    # Дополнительные поля для регистратуры
    visit_type: Optional[str] = Field(default="paid", max_length=16)  # paid, repeat, free
    payment_type: Optional[str] = Field(default="cash", max_length=16)  # cash, card, online
    services: Optional[List[str]] = Field(default_factory=list)  # Список услуг

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

    # Дополнительные поля для регистратуры
    visit_type: Optional[str] = Field(None, max_length=16)  # paid, repeat, free
    payment_type: Optional[str] = Field(None, max_length=16)  # cash, card, online
    services: Optional[List[str]] = None  # Список услуг

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
    patient_name: Optional[str] = None  # Имя пациента (обогащается на бэкенде)

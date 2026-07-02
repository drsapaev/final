from __future__ import annotations

from datetime import date, datetime

from pydantic import Field

from app.schemas.base import ORMModel


class AppointmentBase(ORMModel):
    patient_id: int
    doctor_id: int | None = None
    department: str | None = Field(None, max_length=64)
    appointment_date: date
    appointment_time: str | None = Field(None, max_length=8)  # HH:MM
    notes: str | None = Field(None, max_length=1000)
    status: str = Field(
        default="scheduled", max_length=16
    )  # scheduled, confirmed, cancelled, completed

    # Дополнительные поля для регистратуры
    visit_type: str | None = Field(
        default="paid", max_length=16
    )  # paid, repeat, free
    payment_type: str | None = Field(
        default="cash", max_length=16
    )  # cash, card, online
    services: list[str] | None = Field(default_factory=list)  # Список услуг

    # Поля для интеграции с платежами
    payment_amount: float | None = None
    payment_currency: str | None = Field(default="UZS", max_length=3)
    payment_provider: str | None = Field(None, max_length=32)
    payment_transaction_id: str | None = Field(None, max_length=128)
    payment_webhook_id: int | None = None
    payment_processed_at: datetime | None = None


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(ORMModel):
    doctor_id: int | None = None
    department: str | None = Field(None, max_length=64)
    appointment_date: date | None = None
    appointment_time: str | None = Field(None, max_length=8)
    notes: str | None = Field(None, max_length=1000)
    status: str | None = Field(None, max_length=16)

    # Дополнительные поля для регистратуры
    visit_type: str | None = Field(None, max_length=16)  # paid, repeat, free
    payment_type: str | None = Field(None, max_length=16)  # cash, card, online
    services: list[str] | None = None  # Список услуг

    # Поля для интеграции с платежами
    payment_amount: float | None = None
    payment_currency: str | None = Field(None, max_length=3)
    payment_provider: str | None = Field(None, max_length=32)
    payment_transaction_id: str | None = Field(None, max_length=128)
    payment_webhook_id: int | None = None
    payment_processed_at: datetime | None = None


class Appointment(AppointmentBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None
    patient_name: str | None = None  # Имя пациента (обогащается на бэкенде)

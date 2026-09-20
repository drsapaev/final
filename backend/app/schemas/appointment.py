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


class PatientPortalAppointmentCreate(AppointmentCreate):
    """Round-3 (owner P2): portal-INTERNAL creation schema.

    `department_id` is the SERVER-RESOLVED routing FK. It exists ONLY on
    this internal portal schema so `POST /patients/booking` can persist the
    canonical `departments.id` it resolved and validated itself
    (`_resolve_portal_department`: unknown key / inactive row → 400). It is
    deliberately absent from the shared `AppointmentCreate` (public
    `POST /appointments/` contract): a client-supplied value on the legacy
    endpoint would bypass that validation entirely (inactive/arbitrary
    department ids, nonexistent FK → IntegrityError/500). The general
    endpoint keeps its pre-#3340 contract — no client-owned routing FK.
    """

    department_id: int | None = None


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


class AppointmentHistoryItem(ORMModel):
    """Stable, minimal response item for patient appointment history."""

    id: int
    appointment_date: date
    appointment_time: str | None = Field(None, max_length=8)
    department: str | None = Field(None, max_length=200)
    doctor_id: int | None = None
    status: str = Field(max_length=16)
    notes: str | None = Field(None, max_length=1000)


class Appointment(AppointmentBase):
    id: int
    created_at: datetime
    updated_at: datetime | None = None
    patient_name: str | None = None  # Имя пациента (обогащается на бэкенде)
    # Round-3 (owner P2): the persisted routing FK stays on the READ model —
    # it was moved out of AppointmentBase so the public CREATE contract
    # (`AppointmentCreate`) no longer accepts a client-owned department_id,
    # but readers (schedule, department-schedule, portal previews) still get
    # the canonical departments.id the row was booked under.
    department_id: int | None = None

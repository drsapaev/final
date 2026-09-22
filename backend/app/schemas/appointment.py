from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import Field, field_validator

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
    # Round-4 (owner P1): explicit, correctly-typed department reads.
    # `AppointmentBase.department` is a REQUEST-side display string, but the
    # ORM attribute of the same name is the Department RELATIONSHIP — the
    # first row with a non-NULL department_id (portal booking persists it)
    # turned every canonical read into a response-validation 500. The read
    # model now maps that attribute explicitly (below) and additionally
    # publishes the typed fields backed by the ORM accessors.
    department_key: str | None = None
    department_name: str | None = None

    @field_validator("department", mode="before")
    @classmethod
    def _department_relationship_to_key(cls, value: Any) -> Any:
        """Explicit mapper for the ORM relationship under the legacy name.

        Pydantic's from_attributes reads ``apt.department`` — a Department
        OBJECT once department_id is set. Strings (request echoes, dicts
        re-validated by FastAPI) and None pass through untouched; the
        relationship object maps to its canonical ``Department.key`` so the
        historical response field keeps its `str | null` contract.
        """
        if value is None or isinstance(value, str):
            return value
        return getattr(value, "key", None)

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from app.schemas.base import ORMModel


class VisitBase(ORMModel):
    patient_id: int | None = None
    doctor_id: int | None = None
    status: str = Field(default="open", max_length=16)
    notes: str | None = Field(default=None, max_length=1000)


class VisitCreate(ORMModel):
    patient_id: int | None = None
    doctor_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)


class VisitUpdate(ORMModel):
    patient_id: int | None = None
    doctor_id: int | None = None
    notes: str | None = Field(default=None, max_length=1000)
    status: str | None = Field(None, max_length=16)


class Visit(VisitBase):
    id: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class VisitOut(VisitBase):
    id: int
    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None


class VisitServiceIn(ORMModel):
    code: str | None = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitServiceOut(VisitServiceIn):
    id: int
    visit_id: int
    created_at: datetime | None = None


class VisitWithServices(ORMModel):
    visit: VisitOut
    services: list[VisitServiceOut] | list[VisitServiceIn]

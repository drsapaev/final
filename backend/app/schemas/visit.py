from __future__ import annotations
from app.schemas.base import ORMModel
from datetime import datetime
from typing import List, Optional

from pydantic import Field


class VisitBase(ORMModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: str = Field(default="open", max_length=16)
    notes: Optional[str] = Field(default=None, max_length=1000)


class VisitCreate(ORMModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class VisitUpdate(ORMModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=1000)
    status: Optional[str] = Field(None, max_length=16)


class Visit(VisitBase):
    id: int
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class VisitOut(VisitBase):
    id: int
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class VisitServiceIn(ORMModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitServiceOut(VisitServiceIn):
    id: int
    visit_id: int
    created_at: Optional[datetime] = None


class VisitWithServices(ORMModel):
    visit: VisitOut
    services: List[VisitServiceOut] | List[VisitServiceIn]

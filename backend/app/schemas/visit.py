from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class VisitBase(BaseModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    status: str = Field(default="open", max_length=16)
    notes: Optional[str] = Field(default=None, max_length=1000)


class VisitCreate(BaseModel):
    patient_id: Optional[int] = None
    doctor_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class VisitOut(VisitBase):
    id: int
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class VisitServiceIn(BaseModel):
    code: Optional[str] = Field(default=None, max_length=32)
    name: str = Field(max_length=255)
    price: float = 0.0
    qty: int = 1


class VisitServiceOut(VisitServiceIn):
    id: int
    visit_id: int
    created_at: Optional[datetime] = None


class VisitWithServices(BaseModel):
    visit: VisitOut
    services: List[VisitServiceOut] | List[VisitServiceIn]
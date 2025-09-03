from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import Field

from app.schemas.base import ORMModel


# --- Orders ---
class LabOrderCreate(ORMModel):
    visit_id: Optional[int] = None
    patient_id: Optional[int] = None
    notes: Optional[str] = Field(default=None, max_length=1000)


class LabOrderOut(ORMModel):
    id: int
    visit_id: Optional[int] = None
    patient_id: Optional[int] = None
    status: str = Field(max_length=16)  # ordered|in_progress|done|canceled
    notes: Optional[str] = Field(default=None, max_length=1000)
    created_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


# --- Results ---
class LabResultIn(ORMModel):
    test_code: Optional[str] = Field(default=None, max_length=64)
    test_name: str = Field(max_length=255)
    value: Optional[str] = Field(default=None, max_length=128)
    unit: Optional[str] = Field(default=None, max_length=32)
    ref_range: Optional[str] = Field(default=None, max_length=64)
    abnormal: bool = False


class LabResultOut(LabResultIn):
    id: int
    order_id: int
    created_at: Optional[datetime] = None

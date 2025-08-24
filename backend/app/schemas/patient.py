from __future__ import annotations
from app.schemas.base import ORMModel
from datetime import date, datetime
from typing import Optional

from pydantic import Field


class DailyQueueOut(ORMModel):
    id: int
    date: date
    department: str = Field(max_length=64)
    last_ticket: int
    created_at: Optional[datetime] = None


class QueueEntryBase(ORMModel):
    daily_queue_id: int
    patient_id: Optional[int] = None
    ticket_number: int
    status: str = Field(default="waiting", max_length=16)
    window_no: Optional[str] = Field(default=None, max_length=16)
    notes: Optional[str] = Field(default=None, max_length=512)


class QueueEntryOut(QueueEntryBase):
    id: int
    created_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

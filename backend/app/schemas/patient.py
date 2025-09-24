from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from pydantic import EmailStr, Field

from app.schemas.base import ORMModel


class PatientBase(ORMModel):
    last_name: str = Field(..., max_length=128)
    first_name: str = Field(..., max_length=128)
    middle_name: Optional[str] = Field(None, max_length=128)
    birth_date: Optional[date] = None
    sex: Optional[str] = Field(None, max_length=8)  # M|F|X
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[EmailStr] = None
    doc_number: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=512)


class PatientCreate(PatientBase):
    pass


class PatientUpdate(ORMModel):
    last_name: Optional[str] = Field(None, max_length=128)
    first_name: Optional[str] = Field(None, max_length=128)
    middle_name: Optional[str] = Field(None, max_length=128)
    birth_date: Optional[date] = None
    sex: Optional[str] = Field(None, max_length=8)
    phone: Optional[str] = Field(None, max_length=32)
    email: Optional[EmailStr] = None
    doc_number: Optional[str] = Field(None, max_length=64)
    address: Optional[str] = Field(None, max_length=512)


class Patient(PatientBase):
    id: int
    created_at: datetime


# Схемы для очередей (оставляем существующие)
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

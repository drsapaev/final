from __future__ import annotations
from app.schemas.base import ORMModel
from datetime import datetime, date
from typing import Optional

from pydantic import Field


class AppointmentBase(ORMModel):
    patient_id: int
    doctor_id: Optional[int] = None
    department: Optional[str] = Field(None, max_length=64)
    appointment_date: date
    appointment_time: Optional[str] = Field(None, max_length=8)  # HH:MM
    notes: Optional[str] = Field(None, max_length=1000)
    status: str = Field(default="scheduled", max_length=16)  # scheduled, confirmed, cancelled, completed


class AppointmentCreate(AppointmentBase):
    pass


class AppointmentUpdate(ORMModel):
    doctor_id: Optional[int] = None
    department: Optional[str] = Field(None, max_length=64)
    appointment_date: Optional[date] = None
    appointment_time: Optional[str] = Field(None, max_length=8)
    notes: Optional[str] = Field(None, max_length=1000)
    status: Optional[str] = Field(None, max_length=16)


class Appointment(AppointmentBase):
    id: int
    created_at: datetime
    updated_at: Optional[datetime] = None


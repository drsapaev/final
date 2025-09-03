from __future__ import annotations

from typing import Optional

from pydantic import Field

from app.schemas.base import ORMModel


class ScheduleRowOut(ORMModel):
    id: int
    department: Optional[str] = None
    doctor_id: Optional[int] = None
    weekday: int = Field(ge=0, le=6, description="0=РџРЅ вЂ¦ 6=Р’СЃ")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    room: Optional[str] = None
    capacity_per_hour: Optional[int] = Field(default=None, ge=1, le=200)
    active: bool = True


class ScheduleCreateIn(ORMModel):
    department: Optional[str] = None
    doctor_id: Optional[int] = Field(default=None, ge=1)
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    room: Optional[str] = Field(default=None, max_length=64)
    capacity_per_hour: Optional[int] = Field(default=None, ge=1, le=200)
    active: bool = True

from __future__ import annotations

from pydantic import Field

from app.schemas.base import ORMModel


class ScheduleRowOut(ORMModel):
    id: int
    department: str | None = None
    doctor_id: int | None = None
    weekday: int = Field(ge=0, le=6, description="0=РџРЅ вЂ¦ 6=Р’СЃ")
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    room: str | None = None
    capacity_per_hour: int | None = Field(default=None, ge=1, le=200)
    active: bool = True


class ScheduleCreateIn(ORMModel):
    department: str | None = None
    doctor_id: int | None = Field(default=None, ge=1)
    weekday: int = Field(ge=0, le=6)
    start_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    room: str | None = Field(default=None, max_length=64)
    capacity_per_hour: int | None = Field(default=None, ge=1, le=200)
    active: bool = True

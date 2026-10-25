"""Public read-only availability response contracts."""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict


class PublicBookingAvailabilityOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    slots: list[time]


class PublicBookingAvailabilityErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["public_booking_unavailable"]


class PublicBookingAvailabilityErrorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: PublicBookingAvailabilityErrorDetail

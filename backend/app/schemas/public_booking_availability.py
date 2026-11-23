"""Public read-only availability response contracts."""

from __future__ import annotations

from datetime import date, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.public_booking_settings import PublicBookingMode


class PublicBookingCatalogOptionOut(BaseModel):
    """One currently approved, publicly published booking choice."""

    model_config = ConfigDict(extra="forbid")

    slug: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1)


class PublicBookingCompatiblePairOut(BaseModel):
    """A service/doctor pair accepted by the current booking policy."""

    model_config = ConfigDict(extra="forbid")

    service_slug: str = Field(min_length=1, max_length=120)
    doctor_slug: str = Field(min_length=1, max_length=120)


class PublicBookingOptionsOut(BaseModel):
    """Safe public projection of Admin-approved booking options."""

    model_config = ConfigDict(extra="forbid")

    settings_version: int
    available: bool
    mode: PublicBookingMode | None
    booking_horizon_days: int | None = Field(default=None, ge=1, le=365)
    services: list[PublicBookingCatalogOptionOut]
    doctors: list[PublicBookingCatalogOptionOut]
    compatible_pairs: list[PublicBookingCompatiblePairOut]


class PublicBookingAvailabilityOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    settings_version: int
    slots: list[time]


class PublicBookingAvailabilityErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal["public_booking_unavailable"]


class PublicBookingAvailabilityErrorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: PublicBookingAvailabilityErrorDetail

"""Typed Admin contracts for clinic-wide public booking settings."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicBookingMode(StrEnum):
    CONFIRMED_APPOINTMENT = "confirmed_appointment"
    REGISTRAR_REQUEST = "registrar_request"


class PublicBookingSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    is_enabled: bool
    mode: PublicBookingMode | None
    booking_horizon_days: int | None = Field(default=None, ge=1, le=365)
    service_ids: list[int] = Field(max_length=500)
    doctor_ids: list[int] = Field(max_length=500)

    @model_validator(mode="after")
    def ids_must_be_unique_and_positive(self) -> PublicBookingSettingsUpdate:
        for ids in (self.service_ids, self.doctor_ids):
            if any(item <= 0 for item in ids) or len(ids) != len(set(ids)):
                raise ValueError(
                    "Selected catalog ids must be unique positive integers."
                )
        return self


class PublicBookingOptionOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: int
    label: str | None
    eligible: bool


class PublicBookingSettingsOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int
    is_enabled: bool
    is_ready: bool
    mode: PublicBookingMode | None
    booking_horizon_days: int | None
    service_ids: list[int]
    doctor_ids: list[int]
    services: list[PublicBookingOptionOut]
    doctors: list[PublicBookingOptionOut]
    updated_at: datetime | None = None
    updated_by: int | None = None

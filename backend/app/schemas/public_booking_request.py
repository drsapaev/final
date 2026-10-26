"""Typed patient and staff contracts for non-reserving public booking requests."""

from __future__ import annotations

from datetime import date, datetime, time
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PublicBookingRequestStatus(StrEnum):
    PENDING = "pending"
    NEEDS_NEW_TIME = "needs_new_time"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class PublicBookingRequestCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    service_slug: str = Field(min_length=1, max_length=120)
    doctor_slug: str = Field(min_length=1, max_length=120)
    appointment_date: date
    appointment_time: time
    expected_settings_version: int = Field(ge=0)

    @field_validator("appointment_time")
    @classmethod
    def time_is_tashkent_wall_time(cls, value: time) -> time:
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Appointment time must be a local minute value.")
        return value


class PublicBookingRequestResubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)
    appointment_date: date
    appointment_time: time
    expected_settings_version: int = Field(ge=0)

    @field_validator("appointment_time")
    @classmethod
    def time_is_tashkent_wall_time(cls, value: time) -> time:
        if value.tzinfo is not None or value.second or value.microsecond:
            raise ValueError("Appointment time must be a local minute value.")
        return value


class PublicBookingRequestAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=1)


class PublicBookingRequestEventOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    event_type: Literal[
        "submitted",
        "resubmitted",
        "staff_requested_new_time",
        "rejected",
        "withdrawn",
    ]
    from_status: PublicBookingRequestStatus | None
    to_status: PublicBookingRequestStatus
    previous_appointment_date: date | None
    previous_appointment_time: time | None
    requested_appointment_date: date
    requested_appointment_time: time
    created_at: datetime


class PublicBookingRequestOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    service_slug: str
    doctor_slug: str
    appointment_date: date
    appointment_time: time
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    status: PublicBookingRequestStatus
    settings_version: int
    version: int
    created_at: datetime
    updated_at: datetime
    history: list[PublicBookingRequestEventOut]


class PublicBookingRequestPatientOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    patient_id: int
    patient_display_name: str
    service_name: str
    doctor_display_name: str
    service_slug: str
    doctor_slug: str
    appointment_date: date
    appointment_time: time
    timezone: Literal["Asia/Tashkent"] = "Asia/Tashkent"
    status: PublicBookingRequestStatus
    settings_version: int
    version: int
    created_at: datetime
    updated_at: datetime
    history: list[PublicBookingRequestEventOut]


class PublicBookingRequestListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PublicBookingRequestOut]


class PublicBookingRequestStaffListOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[PublicBookingRequestPatientOut]


class PublicBookingRequestErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: Literal[
        "public_content_not_found",
        "public_booking_unavailable",
        "booking_settings_version_conflict",
        "booking_mode_changed",
        "booking_time_unavailable",
        "booking_request_not_found",
        "booking_request_state_conflict",
        "booking_request_version_conflict",
        "booking_request_idempotency_conflict",
        "booking_request_duplicate",
        "booking_request_rate_limited",
    ]


class PublicBookingRequestErrorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # The global idempotency middleware returns a text detail when a client
    # reuses a key with a different payload; service errors use the typed code.
    detail: PublicBookingRequestErrorDetail | str


class PublicBookingRequestPatientProfileErrorDetail(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: Literal["patient_profile_required"]


class PublicBookingRequestPatientProfileErrorOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    detail: PublicBookingRequestPatientProfileErrorDetail

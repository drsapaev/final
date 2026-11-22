"""Typed Admin contracts for the annual public-booking holiday calendar."""

from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class PublicBookingHoliday(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    is_working_day: bool = False


class PublicBookingCalendarUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)
    holidays: list[PublicBookingHoliday] = Field(max_length=100)

    @model_validator(mode="after")
    def dates_must_be_unique(self) -> PublicBookingCalendarUpdate:
        dates = [holiday.date for holiday in self.holidays]
        if len(dates) != len(set(dates)):
            raise ValueError("Holiday dates must be unique.")
        return self


class PublicBookingCalendarConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_version: int = Field(ge=0)


class PublicBookingCalendarYearOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int
    version: int
    is_confirmed: bool
    holidays: list[PublicBookingHoliday]
    confirmed_at: datetime | None = None
    confirmed_by: int | None = None
    updated_at: datetime | None = None
    updated_by: int | None = None


class PublicBookingCalendarErrorOut(BaseModel):
    detail: dict[str, str]

"""Admin-maintained calendar settings backed by the existing ClinicSettings store."""

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, date, datetime

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.clinic import ClinicSettings
from app.schemas.public_booking_calendar import (
    PublicBookingCalendarUpdate,
    PublicBookingCalendarYearOut,
    PublicBookingHoliday,
)
from app.services.public_booking_availability import BookingCalendar

PUBLIC_BOOKING_CALENDAR_CATEGORY = "booking_calendar"
PUBLIC_BOOKING_CALENDAR_KEY_PREFIX = "public_booking_calendar_year_"
_PUBLIC_BOOKING_CALENDAR_KEY_RE = re.compile(
    rf"^{re.escape(PUBLIC_BOOKING_CALENDAR_KEY_PREFIX)}([0-9]{{4}})$"
)
_MIN_CALENDAR_YEAR = 2000
_MAX_CALENDAR_YEAR = 2200


class PublicBookingCalendarSettingsError(Exception):
    """Expected calendar failure with a safe API status and stable code."""

    def __init__(self, status_code: int, code: str) -> None:
        super().__init__(code)
        self.status_code = status_code
        self.code = code


class _StoredHoliday(BaseModel):
    model_config = ConfigDict(extra="forbid")

    date: date
    is_working_day: bool = False


class _StoredCalendarYear(BaseModel):
    model_config = ConfigDict(extra="forbid")

    year: int = Field(ge=_MIN_CALENDAR_YEAR, le=_MAX_CALENDAR_YEAR)
    version: int = Field(ge=1)
    is_confirmed: bool
    holidays: list[_StoredHoliday] = Field(max_length=100)
    confirmed_at: datetime | None = None
    confirmed_by: int | None = None

    @model_validator(mode="after")
    def stored_state_is_consistent(self) -> _StoredCalendarYear:
        dates = [holiday.date for holiday in self.holidays]
        if len(dates) != len(set(dates)):
            raise ValueError("Stored holiday dates must be unique.")
        has_confirmation_audit = (
            self.confirmed_at is not None and self.confirmed_by is not None
        )
        if self.is_confirmed != has_confirmation_audit:
            raise ValueError("Confirmation state must include its audit fields.")
        if not self.is_confirmed and (
            self.confirmed_at is not None or self.confirmed_by is not None
        ):
            raise ValueError("Unconfirmed calendars cannot keep confirmation fields.")
        return self


def is_public_booking_calendar_setting_key(key: str) -> bool:
    """Return whether a key belongs exclusively to the typed calendar API."""
    return _PUBLIC_BOOKING_CALENDAR_KEY_RE.fullmatch(key) is not None


def _setting_key(year: int) -> str:
    if not _MIN_CALENDAR_YEAR <= year <= _MAX_CALENDAR_YEAR:
        raise PublicBookingCalendarSettingsError(422, "booking_calendar_year_invalid")
    return f"{PUBLIC_BOOKING_CALENDAR_KEY_PREFIX}{year:04d}"


def _load_value(value: object, *, year: int) -> _StoredCalendarYear:
    try:
        stored = _StoredCalendarYear.model_validate(value)
    except ValidationError as exc:
        raise PublicBookingCalendarSettingsError(
            503, "booking_calendar_settings_invalid"
        ) from exc
    if stored.year != year or any(
        holiday.date.year != year for holiday in stored.holidays
    ):
        raise PublicBookingCalendarSettingsError(
            503, "booking_calendar_settings_invalid"
        )
    return stored


def _stored_holidays(
    holidays: Iterable[PublicBookingHoliday], *, year: int
) -> list[_StoredHoliday]:
    normalized: list[_StoredHoliday] = []
    seen: set[date] = set()
    for holiday in holidays:
        if holiday.date.year != year:
            raise PublicBookingCalendarSettingsError(
                422, "booking_calendar_date_outside_year"
            )
        if holiday.date in seen:
            raise PublicBookingCalendarSettingsError(
                422, "booking_calendar_duplicate_date"
            )
        seen.add(holiday.date)
        normalized.append(
            _StoredHoliday(
                date=holiday.date,
                is_working_day=holiday.is_working_day,
            )
        )
    return sorted(normalized, key=lambda holiday: holiday.date)


def _to_output(
    *,
    year: int,
    stored: _StoredCalendarYear | None,
    row: ClinicSettings | None,
) -> PublicBookingCalendarYearOut:
    if stored is None:
        return PublicBookingCalendarYearOut(
            year=year,
            version=0,
            is_confirmed=False,
            holidays=[],
        )
    return PublicBookingCalendarYearOut(
        year=year,
        version=stored.version,
        is_confirmed=stored.is_confirmed,
        holidays=[
            PublicBookingHoliday(
                date=holiday.date,
                is_working_day=holiday.is_working_day,
            )
            for holiday in stored.holidays
        ],
        confirmed_at=stored.confirmed_at,
        confirmed_by=stored.confirmed_by,
        updated_at=row.updated_at if row is not None else None,
        updated_by=row.updated_by if row is not None else None,
    )


def booking_calendar_from_settings(
    rows: Iterable[ClinicSettings],
) -> BookingCalendar:
    """Build the pure availability policy input; invalid years fail closed."""
    confirmed_years: set[int] = set()
    official_holidays: set[date] = set()
    working_exceptions: set[date] = set()

    for row in rows:
        match = _PUBLIC_BOOKING_CALENDAR_KEY_RE.fullmatch(row.key)
        if match is None or row.category != PUBLIC_BOOKING_CALENDAR_CATEGORY:
            continue
        year = int(match.group(1))
        if not _MIN_CALENDAR_YEAR <= year <= _MAX_CALENDAR_YEAR:
            continue
        try:
            stored = _load_value(row.value, year=year)
        except PublicBookingCalendarSettingsError:
            continue
        if not stored.is_confirmed:
            continue

        confirmed_years.add(year)
        for holiday in stored.holidays:
            official_holidays.add(holiday.date)
            if holiday.is_working_day:
                working_exceptions.add(holiday.date)

    return BookingCalendar(
        confirmed_years=frozenset(confirmed_years),
        official_holidays=frozenset(official_holidays),
        working_exceptions=frozenset(working_exceptions),
    )


class PublicBookingCalendarSettingsService:
    """Versioned Admin edits for one year's manually maintained holiday list."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def get_year(self, year: int) -> PublicBookingCalendarYearOut:
        key = _setting_key(year)
        row = (
            self.db.query(ClinicSettings)
            .filter(ClinicSettings.key == key)
            .one_or_none()
        )
        if row is None:
            return _to_output(year=year, stored=None, row=None)
        if row.category != PUBLIC_BOOKING_CALENDAR_CATEGORY:
            raise PublicBookingCalendarSettingsError(
                503, "booking_calendar_settings_invalid"
            )
        stored = _load_value(row.value, year=year)
        return _to_output(year=year, stored=stored, row=row)

    def update_holidays(
        self,
        *,
        year: int,
        update: PublicBookingCalendarUpdate,
        actor_user_id: int,
    ) -> PublicBookingCalendarYearOut:
        key = _setting_key(year)
        holidays = _stored_holidays(update.holidays, year=year)
        row = (
            self.db.query(ClinicSettings)
            .filter(ClinicSettings.key == key)
            .with_for_update()
            .one_or_none()
        )

        if row is None:
            if update.expected_version != 0:
                raise PublicBookingCalendarSettingsError(
                    409, "booking_calendar_version_conflict"
                )
            stored = _StoredCalendarYear(
                year=year,
                version=1,
                is_confirmed=False,
                holidays=holidays,
            )
            row = ClinicSettings(
                key=key,
                category=PUBLIC_BOOKING_CALENDAR_CATEGORY,
                value=stored.model_dump(mode="json"),
                updated_by=actor_user_id,
            )
            self.db.add(row)
            try:
                self.db.commit()
            except IntegrityError as exc:
                self.db.rollback()
                raise PublicBookingCalendarSettingsError(
                    409, "booking_calendar_version_conflict"
                ) from exc
            self.db.refresh(row)
            return _to_output(year=year, stored=stored, row=row)

        if row.category != PUBLIC_BOOKING_CALENDAR_CATEGORY:
            raise PublicBookingCalendarSettingsError(
                503, "booking_calendar_settings_invalid"
            )
        current = _load_value(row.value, year=year)
        if current.version != update.expected_version:
            raise PublicBookingCalendarSettingsError(
                409, "booking_calendar_version_conflict"
            )
        if current.holidays == holidays:
            return _to_output(year=year, stored=current, row=row)

        stored = _StoredCalendarYear(
            year=year,
            version=current.version + 1,
            is_confirmed=False,
            holidays=holidays,
        )
        row.value = stored.model_dump(mode="json")
        row.updated_by = actor_user_id
        self.db.commit()
        self.db.refresh(row)
        return _to_output(year=year, stored=stored, row=row)

    def confirm_year(
        self,
        *,
        year: int,
        expected_version: int,
        actor_user_id: int,
    ) -> PublicBookingCalendarYearOut:
        key = _setting_key(year)
        row = (
            self.db.query(ClinicSettings)
            .filter(ClinicSettings.key == key)
            .with_for_update()
            .one_or_none()
        )
        if row is None:
            raise PublicBookingCalendarSettingsError(
                409, "booking_calendar_must_be_saved_first"
            )
        if row.category != PUBLIC_BOOKING_CALENDAR_CATEGORY:
            raise PublicBookingCalendarSettingsError(
                503, "booking_calendar_settings_invalid"
            )
        current = _load_value(row.value, year=year)
        if current.version != expected_version:
            raise PublicBookingCalendarSettingsError(
                409, "booking_calendar_version_conflict"
            )
        if current.is_confirmed:
            return _to_output(year=year, stored=current, row=row)

        stored = current.model_copy(
            update={
                "version": current.version + 1,
                "is_confirmed": True,
                "confirmed_at": datetime.now(UTC),
                "confirmed_by": actor_user_id,
            }
        )
        row.value = stored.model_dump(mode="json")
        row.updated_by = actor_user_id
        self.db.commit()
        self.db.refresh(row)
        return _to_output(year=year, stored=stored, row=row)

    def load_policy_calendar(self) -> BookingCalendar:
        rows = (
            self.db.query(ClinicSettings)
            .filter(
                ClinicSettings.category == PUBLIC_BOOKING_CALENDAR_CATEGORY,
                ClinicSettings.key.startswith(PUBLIC_BOOKING_CALENDAR_KEY_PREFIX),
            )
            .all()
        )
        return booking_calendar_from_settings(rows)

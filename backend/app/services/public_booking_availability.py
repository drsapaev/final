"""Pure policy for calculating public doctor-booking slot candidates.

This module has no database or API side effects. Callers must provide schedule,
calendar, service-duration, and appointment facts from their canonical owners.
All date/time values represent clinic-local wall time in Asia/Tashkent.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, time
from enum import Enum
from itertools import pairwise
from zoneinfo import ZoneInfo

PUBLIC_BOOKING_TIMEZONE = ZoneInfo("Asia/Tashkent")
PUBLIC_BOOKING_START_STEP_MINUTES = 20
MAX_SERVICE_DURATION_MINUTES = 480
_DAY_MINUTES = 24 * 60


@dataclass(frozen=True)
class TimeWindow:
    """A half-open local-time window such as a doctor break."""

    start: time
    end: time


@dataclass(frozen=True)
class DoctorShift:
    """One active doctor's configured shift for a single weekday."""

    start: time
    end: time
    breaks: tuple[TimeWindow, ...] = ()
    active: bool = True


@dataclass(frozen=True)
class ExistingAppointment:
    """Appointment facts already scoped to the doctor being queried."""

    appointment_date: date
    appointment_time: time | str | None
    duration_minutes_snapshot: int | None
    status: str | Enum | None


@dataclass(frozen=True)
class BookingCalendar:
    """Confirmed years and explicit holiday closures/work exceptions."""

    confirmed_years: frozenset[int] = frozenset()
    official_holidays: frozenset[date] = frozenset()
    working_exceptions: frozenset[date] = frozenset()

    def permits_date(self, target_date: date) -> bool:
        if target_date.year not in self.confirmed_years:
            return False
        return (
            target_date not in self.official_holidays
            or target_date in self.working_exceptions
        )


def available_starts_for_day(
    *,
    target_date: date,
    shift: DoctorShift | None,
    service_duration_minutes: int | None,
    calendar: BookingCalendar | None,
    existing_appointments: Iterable[ExistingAppointment],
) -> list[time]:
    """Return safe start times for one doctor/date, or no slots on bad input.

    The 20-minute grid starts at the beginning of the shift, not at a rounded
    clock boundary. Appointment and break intervals are half-open, so directly
    adjacent intervals do not overlap. Any non-cancelled appointment with an
    unknown/invalid start or duration closes the doctor's whole date. Historical
    durations are never inferred from current service data.
    """
    if shift is None or not shift.active:
        return []
    if not _valid_duration(service_duration_minutes):
        return []
    if calendar is None or not calendar.permits_date(target_date):
        return []

    shift_start = _clock_minutes(shift.start)
    shift_end = _clock_minutes(shift.end)
    if shift_start is None or shift_end is None or shift_end <= shift_start:
        return []

    break_intervals = _validated_break_intervals(
        shift=shift,
        shift_start=shift_start,
        shift_end=shift_end,
    )
    if break_intervals is None:
        return []

    occupied_intervals: list[tuple[int, int]] = []
    for appointment in existing_appointments:
        if appointment.appointment_date != target_date:
            continue
        if _is_cancelled(appointment.status):
            continue

        start = _clock_minutes(appointment.appointment_time)
        duration = appointment.duration_minutes_snapshot
        if start is None or not _valid_duration(duration):
            return []
        end = start + duration
        if end > _DAY_MINUTES:
            return []
        occupied_intervals.append((start, end))

    duration = service_duration_minutes
    latest_start = shift_end - duration
    starts: list[time] = []
    candidate_start = shift_start

    while candidate_start <= latest_start:
        candidate_end = candidate_start + duration
        if not _overlaps_any(candidate_start, candidate_end, break_intervals) and not (
            _overlaps_any(candidate_start, candidate_end, occupied_intervals)
        ):
            local_datetime = datetime.combine(
                target_date,
                time(hour=candidate_start // 60, minute=candidate_start % 60),
                tzinfo=PUBLIC_BOOKING_TIMEZONE,
            )
            starts.append(local_datetime.timetz().replace(tzinfo=None))
        candidate_start += PUBLIC_BOOKING_START_STEP_MINUTES

    return starts


def _clock_minutes(value: time | str | None) -> int | None:
    if isinstance(value, str):
        parsed: time | None = None
        for format_string in ("%H:%M", "%H:%M:%S"):
            try:
                parsed = datetime.strptime(value, format_string).time()
                break
            except ValueError:
                continue
        value = parsed

    if not isinstance(value, time) or value.tzinfo is not None:
        return None
    if value.second != 0 or value.microsecond != 0:
        return None
    return value.hour * 60 + value.minute


def _valid_duration(value: int | None) -> bool:
    return (
        isinstance(value, int)
        and not isinstance(value, bool)
        and 1 <= value <= MAX_SERVICE_DURATION_MINUTES
    )


def _is_cancelled(status: str | Enum | None) -> bool:
    value = getattr(status, "value", status)
    return isinstance(value, str) and value.strip().casefold() == "cancelled"


def _validated_break_intervals(
    *,
    shift: DoctorShift,
    shift_start: int,
    shift_end: int,
) -> list[tuple[int, int]] | None:
    intervals: list[tuple[int, int]] = []
    for pause in shift.breaks:
        pause_start = _clock_minutes(pause.start)
        pause_end = _clock_minutes(pause.end)
        if (
            pause_start is None
            or pause_end is None
            or pause_start >= pause_end
            or pause_start < shift_start
            or pause_end > shift_end
        ):
            return None
        intervals.append((pause_start, pause_end))

    intervals.sort()
    for previous, current in pairwise(intervals):
        if previous[1] > current[0]:
            return None
    return intervals


def _overlaps_any(
    start: int,
    end: int,
    intervals: Iterable[tuple[int, int]],
) -> bool:
    return any(
        start < other_end and end > other_start for other_start, other_end in intervals
    )

from __future__ import annotations

from datetime import date, time
from enum import StrEnum

import pytest

from app.services.public_booking_availability import (
    BookingCalendar,
    DoctorShift,
    ExistingAppointment,
    TimeWindow,
    available_starts_for_day,
)

MONDAY = date(2026, 10, 26)


def confirmed_calendar(
    *, holidays: set[date] | None = None, working: set[date] | None = None
):
    return BookingCalendar(
        confirmed_years=frozenset({MONDAY.year}),
        official_holidays=frozenset(holidays or set()),
        working_exceptions=frozenset(working or set()),
    )


def starts(
    *,
    shift: DoctorShift | None = DoctorShift(time(9), time(11)),
    duration: int | None = 20,
    calendar: BookingCalendar | None = None,
    appointments: tuple[ExistingAppointment, ...] = (),
    target_date: date = MONDAY,
) -> list[str]:
    result = available_starts_for_day(
        target_date=target_date,
        shift=shift,
        service_duration_minutes=duration,
        calendar=calendar or confirmed_calendar(),
        existing_appointments=appointments,
    )
    return [value.strftime("%H:%M") for value in result]


def test_grid_starts_from_shift_start_and_respects_service_end():
    assert starts(shift=DoctorShift(time(9, 10), time(10, 30)), duration=30) == [
        "09:10",
        "09:30",
        "09:50",
    ]


def test_no_shift_or_inactive_shift_fails_closed():
    assert starts(shift=None) == []
    assert starts(shift=DoctorShift(time(9), time(11), active=False)) == []


@pytest.mark.parametrize("duration", [None, 0, -1, 481, True])
def test_invalid_service_duration_fails_closed(duration: int | None):
    assert starts(duration=duration) == []


def test_break_excludes_any_candidate_that_intersects_it():
    shift = DoctorShift(
        time(9),
        time(11),
        breaks=(TimeWindow(time(9, 30), time(10)),),
    )
    assert starts(shift=shift, duration=30) == ["09:00", "10:00", "10:20"]


def test_adjacent_appointment_interval_does_not_overlap():
    appointment = ExistingAppointment(
        appointment_date=MONDAY,
        appointment_time=time(9, 40),
        duration_minutes_snapshot=20,
        status="scheduled",
    )
    assert starts(appointments=(appointment,)) == [
        "09:00",
        "09:20",
        "10:00",
        "10:20",
        "10:40",
    ]


def test_non_cancelled_unknown_duration_closes_the_whole_doctor_day():
    appointment = ExistingAppointment(
        appointment_date=MONDAY,
        appointment_time="10:00",
        duration_minutes_snapshot=None,
        status="scheduled",
    )
    assert starts(appointments=(appointment,)) == []


class CancelledStatus(StrEnum):
    CANCELLED = "cancelled"


def test_cancelled_unknown_duration_does_not_block_slots():
    appointment = ExistingAppointment(
        appointment_date=MONDAY,
        appointment_time=None,
        duration_minutes_snapshot=None,
        status=CancelledStatus.CANCELLED,
    )
    assert starts(appointments=(appointment,)) == [
        "09:00",
        "09:20",
        "09:40",
        "10:00",
        "10:20",
        "10:40",
    ]


@pytest.mark.parametrize(
    ("appointment_time", "duration"),
    [("not-a-time", 20), ("10:00", 0), ("10:00", 481)],
)
def test_invalid_existing_interval_closes_the_whole_day(
    appointment_time: str,
    duration: int,
):
    appointment = ExistingAppointment(
        appointment_date=MONDAY,
        appointment_time=appointment_time,
        duration_minutes_snapshot=duration,
        status="paid",
    )
    assert starts(appointments=(appointment,)) == []


def test_other_date_appointments_do_not_affect_the_target_day():
    appointment = ExistingAppointment(
        appointment_date=date(2026, 10, 27),
        appointment_time=None,
        duration_minutes_snapshot=None,
        status="scheduled",
    )
    assert len(starts(appointments=(appointment,))) == 6


def test_unconfirmed_year_stays_closed_even_with_working_override():
    calendar = BookingCalendar(
        confirmed_years=frozenset(),
        official_holidays=frozenset({MONDAY}),
        working_exceptions=frozenset({MONDAY}),
    )
    assert starts(calendar=calendar) == []


def test_confirmed_holiday_is_closed_until_clinic_marks_it_working():
    holiday_calendar = confirmed_calendar(holidays={MONDAY})
    assert starts(calendar=holiday_calendar) == []

    working_calendar = confirmed_calendar(holidays={MONDAY}, working={MONDAY})
    assert len(starts(calendar=working_calendar)) == 6


def test_invalid_shift_or_break_fails_closed():
    assert starts(shift=DoctorShift(time(11), time(9))) == []
    assert (
        starts(
            shift=DoctorShift(
                time(9),
                time(11),
                breaks=(TimeWindow(time(10), time(9, 30)),),
            )
        )
        == []
    )
    assert (
        starts(
            shift=DoctorShift(
                time(9),
                time(11),
                breaks=(TimeWindow(time(8, 30), time(9, 30)),),
            )
        )
        == []
    )

from __future__ import annotations

from datetime import date, time

import pytest

from app.services.public_booking_availability import BookingCalendar
from app.services.public_booking_availability_service import (
    PublicBookingAvailabilityService,
)

TARGET_DATE = date(2026, 10, 26)  # Monday


class StubAvailabilityRepository:
    def __init__(
        self,
        *,
        schedules: list[tuple[time | None, time | None, object | None]],
        appointments: (
            list[tuple[date, str | None, int | None, str | None]] | None
        ) = None,
    ) -> None:
        self.schedules = schedules
        self.appointments = appointments or []
        self.schedule_query: tuple[int, int] | None = None
        self.appointment_query: tuple[int, date] | None = None

    def list_active_schedules_for_weekday(
        self, *, doctor_id: int, weekday: int
    ) -> list[tuple[time | None, time | None, object | None]]:
        self.schedule_query = (doctor_id, weekday)
        return self.schedules

    def list_appointment_occupancy_for_day(
        self, *, doctor_id: int, target_date: date
    ) -> list[tuple[date, str | None, int | None, str | None]]:
        self.appointment_query = (doctor_id, target_date)
        return self.appointments


def calendar_for(target_date: date = TARGET_DATE) -> BookingCalendar:
    return BookingCalendar(confirmed_years=frozenset({target_date.year}))


def test_uses_doctor_profile_shift_breaks_and_shift_relative_twenty_minute_grid():
    repository = StubAvailabilityRepository(
        schedules=[(time(9, 10), time(11), [{"start": "09:50", "end": "10:10"}])]
    )
    service = PublicBookingAvailabilityService(repository)  # type: ignore[arg-type]

    starts = service.available_starts_for_day(
        doctor_id=41,
        target_date=TARGET_DATE,
        service_duration_minutes=20,
        calendar=calendar_for(),
    )

    assert [value.strftime("%H:%M") for value in starts] == [
        "09:10",
        "09:30",
        "10:10",
        "10:30",
    ]
    assert repository.schedule_query == (41, TARGET_DATE.weekday())
    assert repository.appointment_query == (41, TARGET_DATE)


@pytest.mark.parametrize(
    "schedules",
    [
        [],
        [(time(9), time(11), None), (time(12), time(14), None)],
        [(None, time(11), None)],
        [(time(9), time(11), [{"start": "bad", "end": "10:00"}])],
    ],
)
def test_missing_ambiguous_or_invalid_profile_schedule_fails_closed(schedules):
    repository = StubAvailabilityRepository(schedules=schedules)
    service = PublicBookingAvailabilityService(repository)  # type: ignore[arg-type]

    assert (
        service.available_starts_for_day(
            doctor_id=41,
            target_date=TARGET_DATE,
            service_duration_minutes=20,
            calendar=calendar_for(),
        )
        == []
    )


def test_unconfirmed_calendar_fails_closed_even_when_profile_has_a_shift():
    repository = StubAvailabilityRepository(schedules=[(time(9), time(11), None)])
    service = PublicBookingAvailabilityService(repository)  # type: ignore[arg-type]

    assert (
        service.available_starts_for_day(
            doctor_id=41,
            target_date=TARGET_DATE,
            service_duration_minutes=20,
            calendar=BookingCalendar(),
        )
        == []
    )
    assert repository.appointment_query is None


def test_unknown_existing_duration_blocks_day_and_cancelled_does_not():
    repository = StubAvailabilityRepository(
        schedules=[(time(9), time(10), None)],
        appointments=[(TARGET_DATE, "09:10", None, "scheduled")],
    )
    service = PublicBookingAvailabilityService(repository)  # type: ignore[arg-type]

    assert (
        service.available_starts_for_day(
            doctor_id=41,
            target_date=TARGET_DATE,
            service_duration_minutes=20,
            calendar=calendar_for(),
        )
        == []
    )

    repository.appointments = [(TARGET_DATE, None, None, "cancelled")]
    assert [
        value.strftime("%H:%M")
        for value in service.available_starts_for_day(
            doctor_id=41,
            target_date=TARGET_DATE,
            service_duration_minutes=20,
            calendar=calendar_for(),
        )
    ] == ["09:00", "09:20", "09:40"]


def test_known_existing_duration_is_mapped_to_the_occupied_interval():
    repository = StubAvailabilityRepository(
        schedules=[(time(9), time(11), None)],
        appointments=[(TARGET_DATE, "09:20", 40, "scheduled")],
    )
    service = PublicBookingAvailabilityService(repository)  # type: ignore[arg-type]

    starts = service.available_starts_for_day(
        doctor_id=41,
        target_date=TARGET_DATE,
        service_duration_minutes=20,
        calendar=calendar_for(),
    )

    assert [value.strftime("%H:%M") for value in starts] == [
        "09:00",
        "10:00",
        "10:20",
        "10:40",
    ]

from __future__ import annotations

from datetime import date, datetime, time
from types import SimpleNamespace
from zoneinfo import ZoneInfo

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


class StubPublicSiteRepository:
    def __init__(self):
        self.service = SimpleNamespace(id=11, duration_minutes=20)
        self.doctor = SimpleNamespace(id=22)
        self.lookups: list[tuple[str, str]] = []

    def get_public_service_by_slug(self, slug: str):
        self.lookups.append(("service", slug))
        return self.service

    def get_public_doctor_by_slug(self, slug: str):
        self.lookups.append(("doctor", slug))
        return self.doctor


class StubBookingSettingsRepository:
    def __init__(self, pair_is_allowed: bool = True):
        self.pair_is_allowed = pair_is_allowed
        self.pair_queries: list[tuple[list[int], list[int]]] = []

    def selected_services_match_doctors(
        self, service_ids: list[int], doctor_ids: list[int]
    ) -> bool:
        self.pair_queries.append((service_ids, doctor_ids))
        return self.pair_is_allowed


class StubBookingSettingsService:
    def __init__(self, *, enabled: bool = True, horizon_days: int = 30):
        self.settings = SimpleNamespace(
            is_enabled=enabled,
            is_ready=True,
            booking_horizon_days=horizon_days,
            service_ids=[11],
            doctor_ids=[22],
        )
        self.repository = StubBookingSettingsRepository()
        self.read_count = 0

    def get_settings(self):
        self.read_count += 1
        return self.settings


class StubCalendarSettingsService:
    def __init__(self, calendar: BookingCalendar):
        self.calendar = calendar
        self.read_count = 0

    def load_policy_calendar(self) -> BookingCalendar:
        self.read_count += 1
        return self.calendar


def calendar_for(target_date: date = TARGET_DATE) -> BookingCalendar:
    return BookingCalendar(confirmed_years=frozenset({target_date.year}))


def _not_resource_routed(_service, _target_date: date) -> bool:
    return False


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


def test_public_starts_require_enabled_allowlists_exact_pair_and_confirmed_calendar():
    repository = StubAvailabilityRepository(
        schedules=[(time(9, 10), time(11), [{"start": "09:50", "end": "10:10"}])]
    )
    public_site = StubPublicSiteRepository()
    settings = StubBookingSettingsService(horizon_days=2)
    calendar_settings = StubCalendarSettingsService(calendar_for())
    service = PublicBookingAvailabilityService(
        repository,  # type: ignore[arg-type]
        public_site_repository=public_site,  # type: ignore[arg-type]
        booking_settings_service=settings,  # type: ignore[arg-type]
        calendar_settings_service=calendar_settings,  # type: ignore[arg-type]
        resource_queue_route_policy=_not_resource_routed,
    )

    starts = service.public_starts_for_day(
        service_slug="cardiology-consultation",
        doctor_slug="test-doctor",
        target_date=TARGET_DATE,
        now=datetime(2026, 10, 25, 8, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    assert [value.strftime("%H:%M") for value in starts or []] == [
        "09:10",
        "09:30",
        "10:10",
        "10:30",
    ]
    assert public_site.lookups == [
        ("service", "cardiology-consultation"),
        ("doctor", "test-doctor"),
    ]
    assert settings.repository.pair_queries == [([11], [22])]
    assert calendar_settings.read_count == 1


def test_public_availability_hides_past_starts_on_today():
    repository = StubAvailabilityRepository(schedules=[(time(9), time(10), None)])
    service = PublicBookingAvailabilityService(
        repository,  # type: ignore[arg-type]
        public_site_repository=StubPublicSiteRepository(),  # type: ignore[arg-type]
        booking_settings_service=StubBookingSettingsService(),  # type: ignore[arg-type]
        calendar_settings_service=StubCalendarSettingsService(calendar_for()),  # type: ignore[arg-type]
        resource_queue_route_policy=_not_resource_routed,
    )

    starts = service.public_starts_for_day(
        service_slug="cardiology-consultation",
        doctor_slug="test-doctor",
        target_date=TARGET_DATE,
        now=datetime(2026, 10, 26, 9, 30, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    assert [value.strftime("%H:%M") for value in starts or []] == ["09:40"]


def test_public_availability_hides_a_pair_outside_the_exact_admin_policy():
    repository = StubAvailabilityRepository(schedules=[(time(9), time(10), None)])
    public_site = StubPublicSiteRepository()
    settings = StubBookingSettingsService()
    settings.repository.pair_is_allowed = False
    calendar_settings = StubCalendarSettingsService(calendar_for())
    service = PublicBookingAvailabilityService(
        repository,  # type: ignore[arg-type]
        public_site_repository=public_site,  # type: ignore[arg-type]
        booking_settings_service=settings,  # type: ignore[arg-type]
        calendar_settings_service=calendar_settings,  # type: ignore[arg-type]
        resource_queue_route_policy=_not_resource_routed,
    )

    result = service.public_starts_for_day(
        service_slug="cardiology-consultation",
        doctor_slug="test-doctor",
        target_date=TARGET_DATE,
        now=datetime(2026, 10, 25, 8, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    assert result is None
    assert settings.repository.pair_queries == [([11], [22])]
    assert calendar_settings.read_count == 0


def test_public_availability_hides_resource_routed_pair_for_requested_date():
    repository = StubAvailabilityRepository(schedules=[(time(9), time(10), None)])
    public_site = StubPublicSiteRepository()
    settings = StubBookingSettingsService()
    calendar_settings = StubCalendarSettingsService(calendar_for())
    routing_checks = []

    def routes_to_resource(service, target_date):
        routing_checks.append((service, target_date))
        return True

    availability = PublicBookingAvailabilityService(
        repository,  # type: ignore[arg-type]
        public_site_repository=public_site,  # type: ignore[arg-type]
        booking_settings_service=settings,  # type: ignore[arg-type]
        calendar_settings_service=calendar_settings,  # type: ignore[arg-type]
        resource_queue_route_policy=routes_to_resource,
    )

    result = availability.public_starts_for_day(
        service_slug="cardiology-consultation",
        doctor_slug="test-doctor",
        target_date=TARGET_DATE,
        now=datetime(2026, 10, 25, 8, tzinfo=ZoneInfo("Asia/Tashkent")),
    )

    assert result is None
    assert routing_checks == [(public_site.service, TARGET_DATE)]
    assert calendar_settings.read_count == 0
    assert repository.schedule_query is None


def test_public_availability_fails_closed_when_channel_is_off_or_date_is_outside_horizon():
    repository = StubAvailabilityRepository(schedules=[(time(9), time(10), None)])
    public_site = StubPublicSiteRepository()
    settings = StubBookingSettingsService(enabled=False, horizon_days=1)
    calendar_settings = StubCalendarSettingsService(calendar_for())
    service = PublicBookingAvailabilityService(
        repository,  # type: ignore[arg-type]
        public_site_repository=public_site,  # type: ignore[arg-type]
        booking_settings_service=settings,  # type: ignore[arg-type]
        calendar_settings_service=calendar_settings,  # type: ignore[arg-type]
        resource_queue_route_policy=_not_resource_routed,
    )

    disabled = service.public_starts_for_day(
        service_slug="cardiology-consultation",
        doctor_slug="test-doctor",
        target_date=TARGET_DATE,
        now=datetime(2026, 10, 25, 8, tzinfo=ZoneInfo("Asia/Tashkent")),
    )
    assert disabled == []
    assert public_site.lookups == []

    settings.settings.is_enabled = True
    settings.settings.is_ready = False
    not_ready = service.public_starts_for_day(
        service_slug="cardiology-consultation",
        doctor_slug="test-doctor",
        target_date=TARGET_DATE,
        now=datetime(2026, 10, 25, 8, tzinfo=ZoneInfo("Asia/Tashkent")),
    )
    assert not_ready == []
    assert public_site.lookups == []

    settings.settings.is_ready = True
    outside_horizon = service.public_starts_for_day(
        service_slug="cardiology-consultation",
        doctor_slug="test-doctor",
        target_date=TARGET_DATE,
        now=datetime(2026, 10, 24, 8, tzinfo=ZoneInfo("Asia/Tashkent")),
    )
    assert outside_horizon == []
    assert public_site.lookups == []

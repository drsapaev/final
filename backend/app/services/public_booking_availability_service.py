"""Read-only adapter from Clinic OS schedule data to public slot policy."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, time

from app.models.service import Service
from app.repositories.public_booking_availability_repository import (
    PublicBookingAvailabilityRepository,
)
from app.repositories.public_site_read_repository import PublicSiteReadRepository
from app.services.public_booking_availability import (
    MAX_SERVICE_DURATION_MINUTES,
    PUBLIC_BOOKING_TIMEZONE,
    BookingCalendar,
    DoctorShift,
    ExistingAppointment,
    TimeWindow,
    available_starts_for_day,
)
from app.services.public_booking_calendar_settings import (
    PublicBookingCalendarSettingsService,
)
from app.services.public_booking_settings import PublicBookingSettingsService

ResourceQueueRoutePolicy = Callable[[Service, date], bool]


class PublicBookingAvailabilityService:
    """Calculate candidate starts using the doctor's configured profile shift."""

    def __init__(
        self,
        repository: PublicBookingAvailabilityRepository,
        *,
        public_site_repository: PublicSiteReadRepository | None = None,
        booking_settings_service: PublicBookingSettingsService | None = None,
        calendar_settings_service: PublicBookingCalendarSettingsService | None = None,
        resource_queue_route_policy: ResourceQueueRoutePolicy | None = None,
    ) -> None:
        self.repository = repository
        self.public_site_repository = public_site_repository
        self.booking_settings_service = booking_settings_service
        self.calendar_settings_service = calendar_settings_service
        self.resource_queue_route_policy = resource_queue_route_policy

    def public_starts_for_day(
        self,
        *,
        service_slug: str,
        doctor_slug: str,
        target_date: date,
        now: datetime | None = None,
    ) -> list[time] | None:
        """Return public candidate starts, or ``None`` for an unavailable pair.

        Candidates do not reserve a slot. A future writer must revalidate all
        policy and occupancy facts when the patient confirms an operation.
        """
        if (
            self.public_site_repository is None
            or self.booking_settings_service is None
            or self.calendar_settings_service is None
            or self.resource_queue_route_policy is None
        ):
            raise RuntimeError("Public availability dependencies are not configured.")

        local_now = now or datetime.now(PUBLIC_BOOKING_TIMEZONE)
        if local_now.tzinfo is None or local_now.utcoffset() is None:
            return []
        local_now = local_now.astimezone(PUBLIC_BOOKING_TIMEZONE)

        settings = self.booking_settings_service.get_settings()
        if (
            not settings.is_enabled
            or not settings.is_ready
            or settings.booking_horizon_days is None
        ):
            return []

        days_ahead = (target_date - local_now.date()).days
        if days_ahead < 0 or days_ahead > settings.booking_horizon_days:
            return []

        service = self.public_site_repository.get_public_service_by_slug(service_slug)
        doctor = self.public_site_repository.get_public_doctor_by_slug(doctor_slug)
        if service is None or doctor is None:
            return None
        if (
            service.id not in settings.service_ids
            or doctor.id not in settings.doctor_ids
        ):
            return None
        if not self.booking_settings_service.repository.selected_services_match_doctors(
            [service.id], [doctor.id]
        ):
            return None
        if self.resource_queue_route_policy(service, target_date):
            return None

        calendar = self.calendar_settings_service.load_policy_calendar()
        starts = self.available_starts_for_day(
            doctor_id=doctor.id,
            target_date=target_date,
            service_duration_minutes=service.duration_minutes,
            calendar=calendar,
        )
        if target_date == local_now.date():
            current_time = local_now.timetz().replace(tzinfo=None)
            starts = [start for start in starts if start > current_time]
        return starts

    def available_starts_for_day(
        self,
        *,
        doctor_id: int,
        target_date: date,
        service_duration_minutes: int | None,
        calendar: BookingCalendar | None,
    ) -> list[time]:
        schedule_rows = self.repository.list_active_schedules_for_weekday(
            doctor_id=doctor_id,
            weekday=target_date.weekday(),
        )
        shift = self._shift_from_rows(schedule_rows)
        if (
            shift is None
            or calendar is None
            or not calendar.permits_date(target_date)
            or not isinstance(service_duration_minutes, int)
            or isinstance(service_duration_minutes, bool)
            or not 1 <= service_duration_minutes <= MAX_SERVICE_DURATION_MINUTES
        ):
            return []

        appointments = [
            ExistingAppointment(
                appointment_date=row[0],
                appointment_time=row[1],
                duration_minutes_snapshot=row[2],
                status=row[3],
            )
            for row in self.repository.list_appointment_occupancy_for_day(
                doctor_id=doctor_id,
                target_date=target_date,
            )
        ]
        return available_starts_for_day(
            target_date=target_date,
            shift=shift,
            service_duration_minutes=service_duration_minutes,
            calendar=calendar,
            existing_appointments=appointments,
        )

    @classmethod
    def _shift_from_rows(
        cls,
        rows: list[tuple[time | None, time | None, object | None]],
    ) -> DoctorShift | None:
        # The profile schema is intended to have one active shift per weekday.
        # Ambiguous or malformed data must never create public slots.
        if len(rows) != 1:
            return None

        start, end, raw_breaks = rows[0]
        if not isinstance(start, time) or not isinstance(end, time):
            return None
        breaks = cls._parse_breaks(raw_breaks)
        if breaks is None:
            return None
        return DoctorShift(start=start, end=end, breaks=breaks)

    @staticmethod
    def _parse_breaks(raw_breaks: object) -> tuple[TimeWindow, ...] | None:
        if raw_breaks is None:
            return ()
        if not isinstance(raw_breaks, list):
            return None

        parsed: list[TimeWindow] = []
        for raw_break in raw_breaks:
            if not isinstance(raw_break, dict):
                return None
            start = PublicBookingAvailabilityService._parse_break_time(
                raw_break.get("start")
            )
            end = PublicBookingAvailabilityService._parse_break_time(
                raw_break.get("end")
            )
            if start is None or end is None:
                return None
            parsed.append(TimeWindow(start=start, end=end))
        return tuple(parsed)

    @staticmethod
    def _parse_break_time(value: object) -> time | None:
        if (
            not isinstance(value, str)
            or len(value) != 5
            or value[2] != ":"
            or not value[:2].isdigit()
            or not value[3:].isdigit()
        ):
            return None
        try:
            return time.fromisoformat(value)
        except ValueError:
            return None

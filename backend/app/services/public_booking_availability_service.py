"""Read-only adapter from Clinic OS schedule data to public slot policy."""

from __future__ import annotations

from datetime import date, time

from app.repositories.public_booking_availability_repository import (
    PublicBookingAvailabilityRepository,
)
from app.services.public_booking_availability import (
    MAX_SERVICE_DURATION_MINUTES,
    BookingCalendar,
    DoctorShift,
    ExistingAppointment,
    TimeWindow,
    available_starts_for_day,
)


class PublicBookingAvailabilityService:
    """Calculate candidate starts using the doctor's configured profile shift."""

    def __init__(self, repository: PublicBookingAvailabilityRepository) -> None:
        self.repository = repository

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

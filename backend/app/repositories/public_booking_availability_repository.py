"""Minimal read-only queries for public booking availability."""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Schedule


class PublicBookingAvailabilityRepository:
    """Load only schedule and occupancy fields needed by the slot policy."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_schedules_for_weekday(
        self, *, doctor_id: int, weekday: int
    ) -> list[tuple[time | None, time | None, object | None]]:
        statement = (
            select(Schedule.start_time, Schedule.end_time, Schedule.breaks)
            .where(
                Schedule.doctor_id == doctor_id,
                Schedule.weekday == weekday,
                Schedule.active.is_(True),
            )
            .order_by(Schedule.id)
        )
        return [(row[0], row[1], row[2]) for row in self.db.execute(statement).all()]

    def list_appointment_occupancy_for_day(
        self, *, doctor_id: int, target_date: date
    ) -> list[tuple[date, str | None, int | None, str | None]]:
        """Read no appointment notes, patient details, or payment fields."""
        statement = (
            select(
                Appointment.appointment_date,
                Appointment.appointment_time,
                Appointment.duration_minutes_snapshot,
                Appointment.status,
            )
            .where(
                Appointment.doctor_id == doctor_id,
                Appointment.appointment_date == target_date,
            )
            .order_by(Appointment.appointment_time, Appointment.id)
        )
        return [
            (row[0], row[1], row[2], row[3]) for row in self.db.execute(statement).all()
        ]

"""Minimal read-only queries for public booking availability."""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Doctor, Schedule
from app.models.user import User
from app.models.visit import Visit, VisitService


class PublicBookingAvailabilityRepository:
    """Load only schedule and occupancy fields needed by the slot policy."""

    def __init__(self, db: Session) -> None:
        self.db = db

    def list_active_schedules_for_weekday(
        self, *, doctor_id: int, weekday: int
    ) -> list[tuple[time | None, time | None, object | None]]:
        statement = (
            select(Schedule.start_time, Schedule.end_time, Schedule.breaks)
            .join(Doctor, Schedule.doctor_id == Doctor.id)
            .join(User, Doctor.user_id == User.id)
            .where(
                Schedule.doctor_id == doctor_id,
                Schedule.weekday == weekday,
                Schedule.active.is_(True),
                Doctor.active.is_(True),
                Doctor.show_on_website.is_(True),
                User.is_active.is_(True),
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

    def list_visit_occupancy_for_day(
        self, *, doctor_id: int, target_date: date
    ) -> list[tuple[int, date | None, str | None, int | None, int | None]]:
        """Read visit timing and duration snapshots, without patient or clinical data."""
        statement = (
            select(
                Visit.id,
                Visit.visit_date,
                Visit.visit_time,
                VisitService.qty,
                VisitService.duration_minutes_snapshot,
            )
            .outerjoin(VisitService, VisitService.visit_id == Visit.id)
            .where(
                Visit.doctor_id == doctor_id,
                Visit.visit_date == target_date,
                # A live queue entry can have a Visit row before any clock
                # time is assigned (for example, QR registration). It is not
                # a reservation of a scheduled hour. Never substitute
                # created_at/registration time for visit_time; only Visits
                # with an explicit scheduled time participate in slot overlap.
                Visit.visit_time.is_not(None),
                func.lower(Visit.status).notin_(
                    {"closed", "canceled", "cancelled", "expired"}
                ),
            )
            .order_by(Visit.visit_time, Visit.id, VisitService.id)
        )
        return [
            (row[0], row[1], row[2], row[3], row[4])
            for row in self.db.execute(statement).all()
        ]

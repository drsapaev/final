"""Repository helpers for lightweight analytics endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment_webhook import PaymentWebhook


class AnalyticsSimpleRepository:
    """Encapsulates ORM access for simple analytics APIs."""

    def __init__(self, db: Session):
        self.db = db

    def count_patients(self) -> int:
        return self.db.query(Patient).count()

    def count_appointments(self) -> int:
        return self.db.query(Appointment).count()

    def count_appointments_for_date(self, target_date: date) -> int:
        return (
            self.db.query(Appointment)
            .filter(Appointment.appointment_date == target_date)
            .count()
        )

    def count_payments(self) -> int:
        return self.db.query(PaymentWebhook).count()

    def list_appointment_trends(self, *, start_date: date, end_date: date):
        return (
            self.db.query(
                Appointment.appointment_date.label("date"),
                func.count(Appointment.id).label("count"),
            )
            .filter(
                Appointment.appointment_date >= start_date,
                Appointment.appointment_date <= end_date,
            )
            .group_by(Appointment.appointment_date)
            .order_by(Appointment.appointment_date)
            .all()
        )

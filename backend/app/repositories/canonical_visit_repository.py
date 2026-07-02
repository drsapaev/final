"""Repository helpers for canonical appointment -> visit resolution."""

from __future__ import annotations

from datetime import time

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.visit import Visit


class CanonicalVisitRepository:
    """Encapsulates appointment/visit primitives used by the resolver."""

    def __init__(self, db: Session):
        self.db = db

    def get_appointment(self, appointment_id: int) -> Appointment | None:
        return self.db.query(Appointment).filter(Appointment.id == appointment_id).first()

    def list_visits_for_appointment(self, appointment: Appointment) -> list[Visit]:
        query = self.db.query(Visit).filter(
            Visit.patient_id == appointment.patient_id,
            Visit.visit_date == appointment.appointment_date,
        )
        appointment_times = self._time_match_values(appointment.appointment_time)
        if not appointment_times:
            query = query.filter(Visit.visit_time.is_(None))
        else:
            query = query.filter(Visit.visit_time.in_(appointment_times))

        if appointment.doctor_id is None:
            query = query.filter(Visit.doctor_id.is_(None))
        else:
            query = query.filter(Visit.doctor_id == appointment.doctor_id)
        return query.order_by(Visit.created_at.asc(), Visit.id.asc()).all()

    def create_visit(self, visit: Visit) -> Visit:
        self.db.add(visit)
        self.db.commit()
        self.db.refresh(visit)
        return visit

    @staticmethod
    def _time_match_values(value: str | time | None) -> tuple[str, ...]:
        if value is None:
            return ()
        if isinstance(value, time):
            normalized = value.strftime("%H:%M")
            return (normalized, f"{normalized}:00")

        text = str(value).strip()
        parts = text.split(":")
        values = [text] if text else []
        if len(parts) >= 2:
            try:
                hour = int(parts[0])
                minute = int(parts[1])
            except ValueError:
                return tuple(values)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                normalized = f"{hour:02d}:{minute:02d}"
                values.extend([normalized, f"{normalized}:00"])

        return tuple(dict.fromkeys(values))

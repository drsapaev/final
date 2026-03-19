"""Repository helpers for canonical appointment -> visit resolution."""

from __future__ import annotations

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

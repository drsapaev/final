"""Repository helpers for patient portal endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.lab import LabOrder


class PatientPortalRepository:
    """Encapsulates appointment/lab lookups for patient self-service API."""

    def __init__(self, db: Session):
        self.db = db

    def get_patient_appointment(
        self,
        *,
        appointment_id: int,
        patient_id: int,
    ) -> Appointment | None:
        return (
            self.db.query(Appointment)
            .filter(
                Appointment.id == appointment_id,
                Appointment.patient_id == patient_id,
            )
            .first()
        )

    def list_patient_lab_orders(self, *, patient_id: int) -> list[LabOrder]:
        return self.db.query(LabOrder).filter(LabOrder.patient_id == patient_id).all()


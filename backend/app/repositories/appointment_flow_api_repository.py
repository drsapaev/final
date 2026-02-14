"""Repository helpers for appointment_flow endpoints."""

from __future__ import annotations

from datetime import date
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.appointment import Appointment as AppointmentModel
from app.models.enums import AppointmentStatus
from app.models.visit import Visit


class AppointmentFlowApiRepository:
    """Encapsulates visit-to-appointment resolution and commit primitives."""

    def __init__(self, db: Session):
        self.db = db

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_existing_appointment_for_visit(self, visit: Visit) -> AppointmentModel | None:
        return (
            self.db.query(AppointmentModel)
            .filter(
                and_(
                    AppointmentModel.patient_id == visit.patient_id,
                    AppointmentModel.appointment_date == (visit.visit_date or date.today()),
                    AppointmentModel.doctor_id == visit.doctor_id,
                )
            )
            .first()
        )

    def create_appointment_from_visit(self, visit: Visit) -> AppointmentModel:
        appointment = AppointmentModel(
            patient_id=visit.patient_id,
            appointment_date=visit.visit_date or date.today(),
            appointment_time=visit.visit_time or "09:00",
            status=(
                AppointmentStatus.IN_VISIT
                if visit.status in ["in_progress", "confirmed"]
                else AppointmentStatus.PAID
            ),
            doctor_id=visit.doctor_id,
            department=visit.department,
            notes=visit.notes,
            created_at=visit.created_at,
        )
        self.db.add(appointment)
        self.db.commit()
        self.db.refresh(appointment)
        return appointment

    def refresh(self, instance: Any) -> None:
        self.db.refresh(instance)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

"""Repository helpers for cashier payment creation flow."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.service import Service
from app.models.visit import Visit, VisitService


class PaymentCreateRepository:
    """Encapsulates ORM operations used by payment create service."""

    def __init__(self, db: Session):
        self.db = db

    def get_appointment(self, appointment_id: int) -> Appointment | None:
        return self.db.query(Appointment).filter(Appointment.id == appointment_id).first()

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_visit_by_patient_and_date(
        self, *, patient_id: int, visit_date: date
    ) -> Visit | None:
        return (
            self.db.query(Visit)
            .filter(Visit.patient_id == patient_id, Visit.visit_date == visit_date)
            .first()
        )

    def get_visit_services(self, visit_id: int) -> list[VisitService]:
        return self.db.query(VisitService).filter(VisitService.visit_id == visit_id).all()

    def get_first_visit_service(self, visit_id: int) -> VisitService | None:
        return (
            self.db.query(VisitService).filter(VisitService.visit_id == visit_id).first()
        )

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_payment(self, payment_id: int) -> Payment | None:
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def get_service(self, service_id: int) -> Service | None:
        return self.db.query(Service).filter(Service.id == service_id).first()

    def list_paid_payments_for_visit(self, visit_id: int) -> list[Payment]:
        return (
            self.db.query(Payment)
            .filter(Payment.visit_id == visit_id, Payment.status.in_(["paid", "completed"]))
            .all()
        )

    def commit(self) -> None:
        self.db.commit()

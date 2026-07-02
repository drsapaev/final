"""Repository helpers for payments API."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice
from app.models.service import Service
from app.models.visit import Visit, VisitService

class PaymentsApiRepository:
    """Shared DB session adapter for payments service."""

    def __init__(self, db: Session):
        self.db = db

    def get_appointment_by_id(self, appointment_id: int):
        return self.db.query(Appointment).filter(Appointment.id == appointment_id).first()

    def find_visit_by_patient_and_date(self, *, patient_id: int, visit_date):
        return (
            self.db.query(Visit)
            .filter(
                Visit.patient_id == patient_id,
                Visit.visit_date == visit_date,
            )
            .first()
        )

    def get_visit_by_id(self, visit_id: int):
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def list_visit_services(self, visit_id: int):
        return self.db.query(VisitService).filter(VisitService.visit_id == visit_id).all()

    def get_first_visit_service(self, visit_id: int):
        return self.db.query(VisitService).filter(VisitService.visit_id == visit_id).first()

    def list_paid_payments_for_visit(self, visit_id: int):
        return (
            self.db.query(Payment)
            .filter(
                Payment.visit_id == visit_id,
                Payment.status.in_(["paid", "completed"]),
            )
            .all()
        )

    def get_patient_by_id(self, patient_id: int):
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_service_by_id(self, service_id: int):
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_payment_by_id(self, payment_id: int):
        return self.db.query(Payment).filter(Payment.id == payment_id).first()

    def list_payments_by_visit_id(self, visit_id: int):
        return self.db.query(Payment).filter(Payment.visit_id == visit_id).all()

    def list_pending_invoices(self, *, limit: int = 50):
        return (
            self.db.query(PaymentInvoice)
            .filter(PaymentInvoice.status.in_(["pending", "processing"]))
            .order_by(PaymentInvoice.created_at.desc())
            .limit(limit)
            .all()
        )

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()

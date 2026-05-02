"""Repository helpers for appointments endpoints."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.crud.appointment import appointment as appointment_crud
from app.models import appointment as appointment_models
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.setting import Setting
from app.models.visit import Visit, VisitService
from app.services.service_mapping import get_service_code


class AppointmentsApiRepository:
    """Encapsulates ORM operations for appointments API."""

    def __init__(self, db: Session):
        self.db = db

    def get_queue_setting(self, *, key: str):
        return (
            self.db.query(Setting)
            .filter(Setting.category == "queue", Setting.key == key)
            .with_for_update(read=True)
            .first()
        )

    def add(self, obj) -> None:
        self.db.add(obj)

    def commit(self) -> None:
        self.db.commit()

    def list_appointments(
        self,
        *,
        skip: int,
        limit: int,
        patient_id: int | None,
        doctor_id: int | None,
        department: str | None,
        date_from: str | None,
        date_to: str | None,
    ):
        return appointment_crud.get_appointments(
            self.db,
            skip=skip,
            limit=limit,
            patient_id=patient_id,
            doctor_id=doctor_id,
            department=department,
            date_from=date_from,
            date_to=date_to,
        )

    def get_patient_by_id(self, patient_id: int):
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_service_by_code(self, code: str):
        return (
            self.db.query(Service)
            .filter((Service.code == code) | (Service.service_code == code))
            .first()
        )

    def get_service_by_id(self, service_id: int):
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_mapped_service_code(self, service_id: int) -> str | None:
        return get_service_code(service_id, self.db)

    def list_pending_appointments(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        query = (
            self.db.query(appointment_models.Appointment)
            .filter(appointment_models.Appointment.status.in_(["scheduled", "confirmed", "pending"]))
        )
        if date_from:
            query = query.filter(appointment_models.Appointment.appointment_date >= date_from)
        if date_to:
            query = query.filter(appointment_models.Appointment.appointment_date <= date_to)
        return query.order_by(appointment_models.Appointment.created_at.desc()).all()

    def list_visits_for_pending_payments(
        self,
        *,
        date_from: date | None = None,
        date_to: date | None = None,
    ):
        query = self.db.query(Visit).filter(Visit.discount_mode != "all_free")
        if date_from:
            query = query.filter(Visit.visit_date >= date_from)
        if date_to:
            query = query.filter(Visit.visit_date <= date_to)
        return query.order_by(Visit.created_at.desc()).all()

    def has_paid_invoice_for_visit(self, visit_id: int) -> bool:
        return (
            self.db.query(PaymentInvoiceVisit)
            .join(PaymentInvoice)
            .filter(
                PaymentInvoiceVisit.visit_id == visit_id,
                PaymentInvoice.status == "paid",
            )
            .first()
            is not None
        )

    def list_visit_services(self, visit_id: int):
        return self.db.query(VisitService).filter(VisitService.visit_id == visit_id).all()

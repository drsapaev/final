"""Repository helpers for registrar_notifications endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.appointment import Appointment
from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.online_queue import OnlineQueueEntry
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService


class RegistrarNotificationsApiRepository:
    """Encapsulates ORM lookups for registrar notification contexts."""

    def __init__(self, db: Session):
        self.db = db

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_appointment(self, appointment_id: int) -> Appointment | None:
        return (
            self.db.query(Appointment).filter(Appointment.id == appointment_id).first()
        )

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def list_visit_services(self, visit_id: int) -> list[VisitService]:
        return self.db.query(VisitService).filter(VisitService.visit_id == visit_id).all()

    def get_service_by_code(self, service_code: str) -> Service | None:
        return self.db.query(Service).filter(Service.code == service_code).first()

    def get_price_override(self, price_override_id: int) -> DoctorPriceOverride | None:
        return (
            self.db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == price_override_id)
            .first()
        )

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_service(self, service_id: int) -> Service | None:
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_queue_entry(self, queue_entry_id: int) -> OnlineQueueEntry | None:
        return (
            self.db.query(OnlineQueueEntry)
            .filter(OnlineQueueEntry.id == queue_entry_id)
            .first()
        )

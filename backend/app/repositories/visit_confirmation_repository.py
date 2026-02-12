"""Repository helpers for visit confirmation flow."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from app.crud import online_queue as crud_queue
from app.models.clinic import Doctor
from app.models.patient import Patient
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService


class VisitConfirmationRepository:
    """Encapsulates ORM operations for confirmation service."""

    def __init__(self, db: Session):
        self.db = db

    def get_pending_visit_by_token(self, token: str) -> Visit | None:
        return (
            self.db.query(Visit)
            .filter(Visit.confirmation_token == token, Visit.status == "pending_confirmation")
            .first()
        )

    def get_visit_by_token(self, token: str) -> Visit | None:
        return self.db.query(Visit).filter(Visit.confirmation_token == token).first()

    def get_patient(self, patient_id: int) -> Patient | None:
        return self.db.query(Patient).filter(Patient.id == patient_id).first()

    def get_visit_services(self, visit_id: int) -> list[VisitService]:
        return self.db.query(VisitService).filter(VisitService.visit_id == visit_id).all()

    def get_service(self, service_id: int) -> Service | None:
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_doctor_by_user_id(self, user_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.user_id == user_id).first()

    def get_active_user_by_username(self, username: str) -> User | None:
        return (
            self.db.query(User)
            .filter(User.username == username, User.is_active == True)
            .first()
        )

    def get_or_create_daily_queue(self, day: date, specialist_id: int, queue_tag: str):
        return crud_queue.get_or_create_daily_queue(self.db, day, specialist_id, queue_tag)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, obj) -> None:  # type: ignore[no-untyped-def]
        self.db.refresh(obj)

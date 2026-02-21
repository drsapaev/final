"""Repository helpers for dental API."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService

class DentalApiRepository:
    """Shared DB session adapter for dental service."""

    def __init__(self, db: Session):
        self.db = db

    def list_registrars(self):
        return self.db.query(User).filter(User.role == "Registrar").all()

    def get_visit_by_id(self, visit_id: int):
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_service_by_id(self, service_id: int):
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_doctor_by_user_id(self, user_id: int):
        return self.db.query(Doctor).filter(Doctor.user_id == user_id).first()

    def get_doctor_by_id(self, doctor_id: int):
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def list_price_overrides_for_doctor(
        self,
        *,
        doctor_id: int,
        visit_id: int | None,
        status: str | None,
        limit: int,
    ):
        query = self.db.query(DoctorPriceOverride).filter(
            DoctorPriceOverride.doctor_id == doctor_id
        )
        if visit_id:
            query = query.filter(DoctorPriceOverride.visit_id == visit_id)
        if status:
            query = query.filter(DoctorPriceOverride.status == status)
        return query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()

    def get_price_override_by_id(self, override_id: int):
        return (
            self.db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.id == override_id)
            .first()
        )

    def get_visit_service(self, *, visit_id: int, service_id: int):
        return (
            self.db.query(VisitService)
            .filter(
                VisitService.visit_id == visit_id,
                VisitService.service_id == service_id,
            )
            .first()
        )

    def list_pending_price_overrides(self, *, limit: int):
        return (
            self.db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.status == "pending")
            .order_by(DoctorPriceOverride.created_at.desc())
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

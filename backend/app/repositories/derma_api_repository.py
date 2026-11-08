"""Repository helpers for derma endpoints."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.service import Service
from app.models.visit import Visit, VisitService


class DermaApiRepository:
    """Encapsulates ORM access for derma price override flows."""

    def __init__(self, db: Session):
        self.db = db

    def get_visit(self, visit_id: int) -> Visit | None:
        return self.db.query(Visit).filter(Visit.id == visit_id).first()

    def get_service(self, service_id: int) -> Service | None:
        return self.db.query(Service).filter(Service.id == service_id).first()

    def get_visit_service(
        self, *, visit_id: int, service_id: int
    ) -> VisitService | None:
        """DERMAPRICE-BE-001: membership probe — is the catalogue service
        actually attached to the visit (VisitService is the real
        visit↔service association)."""
        return (
            self.db.query(VisitService)
            .filter(
                VisitService.visit_id == visit_id,
                VisitService.service_id == service_id,
            )
            .first()
        )

    def get_doctor_by_user_id(self, user_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.user_id == user_id).first()

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def create_price_override(
        self,
        *,
        visit_id: int,
        doctor_id: int,
        service_id: int,
        original_price: Decimal,
        new_price: Decimal,
        reason: str,
        details: str | None,
        visit_price_before: Decimal | None = None,
    ) -> DoctorPriceOverride:
        price_override = DoctorPriceOverride(
            visit_id=visit_id,
            doctor_id=doctor_id,
            service_id=service_id,
            original_price=original_price,
            new_price=new_price,
            reason=reason,
            details=details,
            visit_price_before=visit_price_before,
            status="pending",
        )
        self.db.add(price_override)
        self.db.commit()
        self.db.refresh(price_override)
        return price_override

    def list_price_overrides(
        self,
        *,
        doctor_id: int | None,
        visit_id: int | None,
        status: str | None,
        limit: int,
    ) -> list[DoctorPriceOverride]:
        # DERMAPRICE-BE-004: doctor_id=None → aggregated view (Admin without
        # a Doctor profile — DERMA_ROLES includes Admin for the LIST route).
        query = self.db.query(DoctorPriceOverride)
        if doctor_id is not None:
            query = query.filter(DoctorPriceOverride.doctor_id == doctor_id)

        if visit_id:
            query = query.filter(DoctorPriceOverride.visit_id == visit_id)
        if status:
            query = query.filter(DoctorPriceOverride.status == status)

        return query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()

    def rollback(self) -> None:
        self.db.rollback()

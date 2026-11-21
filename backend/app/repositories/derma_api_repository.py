"""Repository helpers for derma endpoints."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.profile_contact_security import (
    check_bearer_expiry,
    check_profile_bearer,
)


class DermaApiRepository:
    """Encapsulates ORM access for derma price override flows."""

    def __init__(self, db: Session):
        self.db = db

    def reserve_request_writer(self):
        if self.db.get_bind().dialect.name == "sqlite":
            # SQLite has no row-level FOR UPDATE. A no-match UPDATE takes
            # the write reservation without changing a row or firing triggers.
            self.db.execute(text("UPDATE users SET id=id WHERE 0"))

    def lock_request_user(self, context):
        actor = (self.db.query(User).filter(User.id == context.user_id)
                 .with_for_update().populate_existing().first())
        if actor is None:
            from app.services.profile_contact_security import ProfileBearerInvalid
            raise ProfileBearerInvalid("Bearer session unavailable")
        check_profile_bearer(self.db, actor, context)
        return actor

    def lock_request_doctor(self, user_id):
        return (self.db.query(Doctor).filter(Doctor.user_id == user_id)
                .with_for_update().populate_existing().first())

    def lock_request_visit(self, visit_id):
        return (self.db.query(Visit).filter(Visit.id == visit_id)
                .with_for_update().populate_existing().first())

    def lock_request_service(self, service_id):
        return (self.db.query(Service).filter(Service.id == service_id)
                .with_for_update().populate_existing().first())

    def request_visit_services(self, visit_id, service_id):
        # Never wait for a child row after taking Visit: 0102 child triggers
        # acquire child -> Visit, so a blocking child lock would deadlock.
        return (self.db.query(VisitService)
                .filter(VisitService.visit_id == visit_id, VisitService.service_id == service_id)
                .order_by(VisitService.id).populate_existing().all())

    def protect_target_fk(self, visit_id, service_id, target_id):
        query = (self.db.query(VisitService)
                 .filter(VisitService.id == target_id, VisitService.visit_id == visit_id,
                         VisitService.service_id == service_id).populate_existing())
        if self.db.get_bind().dialect.name == "postgresql":
            # FK INSERT takes KEY SHARE. Acquire it NOWAIT to fail fast rather
            # than deadlock with an in-flight child DELETE waiting on Visit.
            query = query.with_for_update(read=True, key_share=True, nowait=True)
        return query.first()

    def commit_request(self, context):
        check_bearer_expiry(context)
        self.db.commit()

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

    def has_pending_override(self, *, visit_id: int, service_id: int, target_id: int) -> bool:
        """Block a second decision on the same row or an unbound legacy request."""
        return (
            self.db.query(DoctorPriceOverride)
            .filter(
                DoctorPriceOverride.visit_id == visit_id,
                DoctorPriceOverride.service_id == service_id,
                DoctorPriceOverride.status == "pending",
                (DoctorPriceOverride.target_visit_service_id == target_id)
                | (DoctorPriceOverride.target_visit_service_id.is_(None))
                | (DoctorPriceOverride.target_scope.is_(None))
                | (DoctorPriceOverride.target_scope != "visit_service"),
            )
            .first()
            is not None
        )

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
        target_visit_service_id: int,
        visit_context_epoch: int,
        doctor_owner_user_id: int,
        doctor_owner_generation: int,
        price_context_generation: int,
        price_line_generation: int,
        price_owner_generation: int,
        requester_user_id: int,
        requester_auth_epoch: int,
        context,
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
            target_scope="visit_service",
            target_visit_service_id=target_visit_service_id,
            visit_context_epoch=visit_context_epoch,
            doctor_owner_user_id=doctor_owner_user_id,
            doctor_owner_generation=doctor_owner_generation,
            price_context_generation=price_context_generation,
            price_line_generation=price_line_generation,
            price_owner_generation=price_owner_generation,
            doctor_user_auth_epoch=requester_auth_epoch,
            requester_type="doctor", requester_user_id=requester_user_id,
            requester_user_id_snapshot=requester_user_id, requester_auth_epoch=requester_auth_epoch,
            status="pending",
        )
        self.db.add(price_override)
        # Materialize the response in the same pinned, locked transaction.
        # A refresh after commit would run on a new, unpinned search path.
        self.db.flush()
        self.db.refresh(price_override)
        self.db.expunge(price_override)
        self.commit_request(context)
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

"""Repository helpers for dental endpoints."""

from __future__ import annotations

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


class DentalApiRepository:
    """Encapsulates ORM operations used by dental API service."""

    def __init__(self, db: Session):
        self.db = db

    def list_registrars(self) -> list[User]:
        return self.db.query(User).filter(User.role == "Registrar").all()

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

    def get_doctor(self, doctor_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.id == doctor_id).first()

    def get_doctor_by_user_id(self, user_id: int) -> Doctor | None:
        return self.db.query(Doctor).filter(Doctor.user_id == user_id).first()

    def add(self, obj) -> None:
        self.db.add(obj)

    def flush(self) -> None:
        self.db.flush()

    def get_price_override(self, override_id: int) -> DoctorPriceOverride | None:
        return self.db.query(DoctorPriceOverride).filter(DoctorPriceOverride.id == override_id).first()

    def list_price_overrides_for_doctor(
        self,
        *,
        doctor_id: int,
        visit_id: int | None,
        status: str | None,
        limit: int,
    ) -> list[DoctorPriceOverride]:
        query = self.db.query(DoctorPriceOverride).filter(
            DoctorPriceOverride.doctor_id == doctor_id
        )
        if visit_id:
            query = query.filter(DoctorPriceOverride.visit_id == visit_id)
        if status:
            query = query.filter(DoctorPriceOverride.status == status)
        return query.order_by(DoctorPriceOverride.created_at.desc()).limit(limit).all()

    def get_visit_service(self, *, visit_id: int, service_id: int) -> VisitService | None:
        return (
            self.db.query(VisitService)
            .filter(
                VisitService.visit_id == visit_id,
                VisitService.service_id == service_id,
            )
            .first()
        )

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

    def list_pending_price_overrides(
        self, *, limit: int, offset: int = 0
    ) -> list[DoctorPriceOverride]:
        # REGPRICE-BE-004 (audit #3892, group 16): deterministic
        # (created_at DESC, id DESC) order so offset pagination is stable
        # across pages even for same-second timestamps.
        return (
            self.db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.status == "pending")
            .order_by(DoctorPriceOverride.created_at.desc(), DoctorPriceOverride.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count_pending_price_overrides(self) -> int:
        return (
            self.db.query(DoctorPriceOverride)
            .filter(DoctorPriceOverride.status == "pending")
            .count()
        )

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()

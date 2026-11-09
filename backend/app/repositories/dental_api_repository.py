"""Repository helpers for dental endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.clinic import Doctor
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.service import Service
from app.models.telegram_config import TelegramUser
from app.models.user import User
from app.models.visit import Visit, VisitService


class DentalApiRepository:
    """Encapsulates ORM operations used by dental API service."""

    def __init__(self, db: Session):
        self.db = db

    def list_registrars(self) -> list[User]:
        return self.db.query(User).filter(User.role == "Registrar").all()

    def get_telegram_chat_ids_by_user_ids(
        self, user_ids: list[int]
    ) -> dict[int, int]:
        """DENTPRICE-BE-001 (audit #3892, group 17): the REAL user↔chat
        association lives in ``telegram_users`` (``user_id`` ↔ ``chat_id``);
        the ``User`` model has no telegram column. Returns only active,
        unblocked links with notifications enabled."""
        if not user_ids:
            return {}
        rows = (
            self.db.query(TelegramUser)
            .filter(
                TelegramUser.user_id.in_(user_ids),
                TelegramUser.active.is_(True),
                TelegramUser.blocked.is_(False),
                TelegramUser.notifications_enabled.is_(True),
            )
            .all()
        )
        return {row.user_id: row.chat_id for row in rows if row.user_id is not None}

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

    def has_pending_override(self, *, visit_id: int, service_id: int) -> bool:
        """REGPRICE-BE-003 (audit 3892, group 16): creation-side probe —
        another pending override for the same visit/service must block a
        second intent (reverse-order approval hazard)."""
        return (
            self.db.query(DoctorPriceOverride)
            .filter(
                DoctorPriceOverride.visit_id == visit_id,
                DoctorPriceOverride.service_id == service_id,
                DoctorPriceOverride.status == "pending",
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

"""Service layer for derma endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.derma_api_repository import DermaApiRepository
from app.services.price_override_approval import (
    PriceOverrideApprovalError,
    ensure_no_pending_override_for_visit_service,
)


@dataclass
class DermaApiDomainError(Exception):
    status_code: int
    detail: str


class DermaApiService:
    """Handles business rules for derma price override endpoints."""

    def __init__(
        self,
        db: Session,
        repository: DermaApiRepository | None = None,
    ):
        self.repository = repository or DermaApiRepository(db)

    def _visit_belongs_to_doctor(self, *, visit, doctor, user_id: int) -> bool:
        visit_doctor_id = getattr(visit, "doctor_id", None)
        if visit_doctor_id == getattr(doctor, "id", None):
            return True

        get_doctor = getattr(self.repository, "get_doctor", None)
        assigned_doctor = get_doctor(user_id) if get_doctor else None
        # Some legacy visit writers stored User.id in doctor_id. Allow that only
        # when the value does not target another real Doctor row.
        return assigned_doctor is None and visit_doctor_id == user_id

    def create_price_override(self, *, override_data, user_id: int):
        visit = self.repository.get_visit(override_data.visit_id)
        if not visit:
            raise DermaApiDomainError(404, "Визит не найден")

        service = self.repository.get_service(override_data.service_id)
        if not service:
            raise DermaApiDomainError(404, "Услуга не найдена")
        if not service.allow_doctor_price_override:
            raise DermaApiDomainError(
                400,
                "Данная услуга не разрешает изменение цены врачом",
            )

        # DERMAPRICE-BE-001 (audit #3892, group 15): the requested service
        # must be ATTACHED to the selected visit (VisitService is the real
        # visit↔service association). Without this check a request for an
        # unattached catalogue service entered the pending-review workflow
        # and the shared approval then marked it approved while silently
        # skipping the price update — a false-positive financial workflow.
        visit_service = self.repository.get_visit_service(
            visit_id=override_data.visit_id,
            service_id=override_data.service_id,
        )
        if visit_service is None:
            raise DermaApiDomainError(
                409,
                "Услуга не привязана к выбранному визиту",
            )

        # REGPRICE-BE-003 (audit #3892, group 16): two sequential pending
        # overrides for the same visit/service can be approved in reverse
        # order — each approval validated against the SAME captured
        # before-price, silently overwriting the newer intent. Creation is
        # refused while one intent is still awaiting review.
        try:
            ensure_no_pending_override_for_visit_service(
                self.repository.db,
                visit_id=override_data.visit_id,
                service_id=override_data.service_id,
            )
        except PriceOverrideApprovalError as exc:
            raise DermaApiDomainError(exc.status_code, exc.detail) from exc

        doctor = self.repository.get_doctor_by_user_id(user_id)
        if not doctor:
            raise DermaApiDomainError(404, "Врач не найден")
        if doctor.specialty not in ["dermatology", "cosmetology"]:
            raise DermaApiDomainError(
                403,
                "Только дерматолог-косметолог может изменять цены процедур",
            )

        if not self._visit_belongs_to_doctor(visit=visit, doctor=doctor, user_id=user_id):
            raise DermaApiDomainError(403, "Access denied")

        return self.repository.create_price_override(
            visit_id=override_data.visit_id,
            doctor_id=doctor.id,
            service_id=override_data.service_id,
            original_price=service.price or Decimal("0"),
            new_price=override_data.new_price,
            reason=override_data.reason,
            details=override_data.details,
            # DERMAPRICE-BE-002: capture the visit's ACTUAL price for the
            # truthful before-reference; original_price keeps its immutable
            # catalogue-reference semantics.
            visit_price_before=visit_service.price,
        )

    def get_price_overrides(
        self,
        *,
        user_id: int,
        visit_id: int | None,
        status: str | None,
        limit: int,
        is_admin: bool = False,
    ):
        doctor = self.repository.get_doctor_by_user_id(user_id)
        if not doctor:
            if is_admin:
                # DERMAPRICE-BE-004 (audit #3892, group 15): DERMA_ROLES
                # includes Admin for the LIST route — an administrator
                # without a linked Doctor row gets the authorized aggregated
                # view instead of a domain 404 from doctor resolution.
                # CREATE stays dermatologist-profile-gated by design.
                return self.repository.list_price_overrides(
                    doctor_id=None,
                    visit_id=visit_id,
                    status=status,
                    limit=limit,
                )
            raise DermaApiDomainError(404, "Врач не найден")

        return self.repository.list_price_overrides(
            doctor_id=doctor.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )

    def rollback(self) -> None:
        self.repository.rollback()

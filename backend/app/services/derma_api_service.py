"""Service layer for derma endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.repositories.derma_api_repository import DermaApiRepository


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

        doctor = self.repository.get_doctor_by_user_id(user_id)
        if not doctor:
            raise DermaApiDomainError(404, "Врач не найден")
        if doctor.specialty not in ["dermatology", "cosmetology"]:
            raise DermaApiDomainError(
                403,
                "Только дерматолог-косметолог может изменять цены процедур",
            )

        return self.repository.create_price_override(
            visit_id=override_data.visit_id,
            doctor_id=doctor.id,
            service_id=override_data.service_id,
            original_price=service.price or Decimal("0"),
            new_price=override_data.new_price,
            reason=override_data.reason,
            details=override_data.details,
        )

    def get_price_overrides(
        self,
        *,
        user_id: int,
        visit_id: int | None,
        status: str | None,
        limit: int,
    ):
        doctor = self.repository.get_doctor_by_user_id(user_id)
        if not doctor:
            raise DermaApiDomainError(404, "Врач не найден")

        return self.repository.list_price_overrides(
            doctor_id=doctor.id,
            visit_id=visit_id,
            status=status,
            limit=limit,
        )

    def rollback(self) -> None:
        self.repository.rollback()

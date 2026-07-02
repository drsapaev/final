"""Service layer for discount_benefits endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from app.repositories.discount_benefits_api_repository import (
    DiscountBenefitsApiRepository,
)
from app.services.discount_benefits_service import DiscountBenefitsService


@dataclass
class DiscountBenefitsApiDomainError(Exception):
    status_code: int
    detail: str


class DiscountBenefitsApiService:
    """Builds endpoint payloads and updates for discount/benefit APIs."""

    def __init__(
        self,
        db: Session,
        repository: DiscountBenefitsApiRepository | None = None,
        discount_service: DiscountBenefitsService | None = None,
    ):
        self.repository = repository or DiscountBenefitsApiRepository(db)
        self.discount_service = discount_service or DiscountBenefitsService(db)

    def get_discounts(
        self,
        *,
        active_only: bool,
        service_ids: list[int] | None,
    ):
        if active_only:
            return self.discount_service.get_active_discounts(service_ids)
        return self.repository.list_all_discounts()

    def update_discount(self, *, discount_id: int, update_data: dict) -> None:
        discount = self.repository.get_discount(discount_id)
        if not discount:
            raise DiscountBenefitsApiDomainError(404, "Скидка не найдена")

        for field, value in update_data.items():
            setattr(discount, field, value)
        discount.updated_at = datetime.now()
        self.repository.commit()

    def delete_discount(self, *, discount_id: int) -> None:
        discount = self.repository.get_discount(discount_id)
        if not discount:
            raise DiscountBenefitsApiDomainError(404, "Скидка не найдена")

        discount.is_active = False
        discount.updated_at = datetime.now()
        self.repository.commit()

    def list_benefits(self, *, active_only: bool):
        return self.repository.list_benefits(active_only=active_only)

    def list_loyalty_programs(self, *, active_only: bool):
        return self.repository.list_loyalty_programs(active_only=active_only)

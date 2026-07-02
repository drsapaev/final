"""Repository helpers for discount_benefits endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.discount_benefits import Benefit, Discount, LoyaltyProgram


class DiscountBenefitsApiRepository:
    """Encapsulates ORM access for endpoint-specific discount/benefit operations."""

    def __init__(self, db: Session):
        self.db = db

    def list_all_discounts(self) -> list[Discount]:
        return self.db.query(Discount).all()

    def get_discount(self, discount_id: int) -> Discount | None:
        return self.db.query(Discount).filter(Discount.id == discount_id).first()

    def list_benefits(self, *, active_only: bool) -> list[Benefit]:
        query = self.db.query(Benefit)
        if active_only:
            query = query.filter(Benefit.is_active.is_(True))
        return query.all()

    def list_loyalty_programs(self, *, active_only: bool) -> list[LoyaltyProgram]:
        query = self.db.query(LoyaltyProgram)
        if active_only:
            query = query.filter(LoyaltyProgram.is_active.is_(True))
        return query.all()

    def commit(self) -> None:
        self.db.commit()

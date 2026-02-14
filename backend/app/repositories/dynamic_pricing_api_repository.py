"""Repository helpers for dynamic pricing endpoints."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dynamic_pricing import (
    PriceHistory,
    PricingRule,
    PricingRuleService,
    PricingRuleType,
    ServicePackage,
)


class DynamicPricingApiRepository:
    """Encapsulates ORM access for dynamic pricing API service."""

    def __init__(self, db: Session):
        self.db = db

    def add_pricing_rule_service(self, *, rule_id: int, service_id: int) -> None:
        self.db.add(PricingRuleService(rule_id=rule_id, service_id=service_id))

    def list_pricing_rules(
        self,
        *,
        skip: int,
        limit: int,
        rule_type: PricingRuleType | None,
        is_active: bool | None,
    ) -> list[PricingRule]:
        query = self.db.query(PricingRule)
        if rule_type:
            query = query.filter(PricingRule.rule_type == rule_type)
        if is_active is not None:
            query = query.filter(PricingRule.is_active == is_active)
        return query.offset(skip).limit(limit).all()

    def get_pricing_rule(self, rule_id: int) -> PricingRule | None:
        return self.db.query(PricingRule).filter(PricingRule.id == rule_id).first()

    def delete(self, obj) -> None:
        self.db.delete(obj)

    def list_service_packages(
        self,
        *,
        skip: int,
        limit: int,
        is_active: bool | None,
    ) -> list[ServicePackage]:
        query = self.db.query(ServicePackage)
        if is_active is not None:
            query = query.filter(ServicePackage.is_active == is_active)
        return query.offset(skip).limit(limit).all()

    def get_service_package(self, package_id: int) -> ServicePackage | None:
        return self.db.query(ServicePackage).filter(ServicePackage.id == package_id).first()

    def list_price_history(
        self,
        *,
        service_id: int,
        skip: int,
        limit: int,
    ) -> list[PriceHistory]:
        return (
            self.db.query(PriceHistory)
            .filter(PriceHistory.service_id == service_id)
            .order_by(PriceHistory.changed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()

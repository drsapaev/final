"""Repository helpers for dynamic pricing API."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.dynamic_pricing import (
    PriceHistory,
    PricingRule,
    PricingRuleService,
    ServicePackage,
)

class DynamicPricingApiRepository:
    """Shared DB session adapter for dynamic pricing service."""

    def __init__(self, db: Session):
        self.db = db

    def add_pricing_rule_services(self, *, rule_id: int, service_ids: list[int]) -> None:
        for service_id in service_ids:
            self.db.add(PricingRuleService(rule_id=rule_id, service_id=service_id))

    def list_pricing_rules(self, *, skip: int, limit: int, rule_type=None, is_active=None):
        query = self.db.query(PricingRule)
        if rule_type:
            query = query.filter(PricingRule.rule_type == rule_type)
        if is_active is not None:
            query = query.filter(PricingRule.is_active == is_active)
        return query.offset(skip).limit(limit).all()

    def get_pricing_rule_by_id(self, rule_id: int):
        return self.db.query(PricingRule).filter(PricingRule.id == rule_id).first()

    def list_service_packages(self, *, skip: int, limit: int, is_active=None):
        query = self.db.query(ServicePackage)
        if is_active is not None:
            query = query.filter(ServicePackage.is_active == is_active)
        return query.offset(skip).limit(limit).all()

    def get_service_package_by_id(self, package_id: int):
        return self.db.query(ServicePackage).filter(ServicePackage.id == package_id).first()

    def list_price_history(self, *, service_id: int, skip: int, limit: int):
        return (
            self.db.query(PriceHistory)
            .filter(PriceHistory.service_id == service_id)
            .order_by(PriceHistory.changed_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def add(self, obj) -> None:
        self.db.add(obj)

    def delete(self, obj) -> None:
        self.db.delete(obj)

    def commit(self) -> None:
        self.db.commit()

    def refresh(self, obj) -> None:
        self.db.refresh(obj)

    def rollback(self) -> None:
        self.db.rollback()

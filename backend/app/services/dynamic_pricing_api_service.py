"""Service layer for dynamic pricing endpoints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.repositories.dynamic_pricing_api_repository import DynamicPricingApiRepository
from app.services.dynamic_pricing_service import DynamicPricingService


@dataclass
class DynamicPricingApiDomainError(Exception):
    status_code: int
    detail: str


class DynamicPricingApiService:
    """Coordinates dynamic pricing domain service and endpoint payload logic."""

    def __init__(
        self,
        db: Session,
        repository: DynamicPricingApiRepository | None = None,
        pricing_service: DynamicPricingService | None = None,
    ):
        self.repository = repository or DynamicPricingApiRepository(db)
        self.pricing_service = pricing_service or DynamicPricingService(db)

    def create_pricing_rule(self, *, payload: dict[str, Any], current_user_id: int):
        rule = self.pricing_service.create_pricing_rule(
            name=payload["name"],
            description=payload.get("description"),
            rule_type=payload["rule_type"],
            discount_type=payload["discount_type"],
            discount_value=payload["discount_value"],
            start_date=payload.get("start_date"),
            end_date=payload.get("end_date"),
            start_time=payload.get("start_time"),
            end_time=payload.get("end_time"),
            days_of_week=payload.get("days_of_week"),
            min_quantity=payload.get("min_quantity", 1),
            max_quantity=payload.get("max_quantity"),
            min_amount=payload.get("min_amount"),
            priority=payload.get("priority", 0),
            max_uses=payload.get("max_uses"),
            created_by=current_user_id,
        )
        for service_id in payload["service_ids"]:
            self.repository.add_pricing_rule_service(rule_id=rule.id, service_id=service_id)
        self.repository.commit()
        return rule

    def list_pricing_rules(
        self,
        *,
        skip: int,
        limit: int,
        rule_type,
        is_active: bool | None,
    ):
        return self.repository.list_pricing_rules(
            skip=skip,
            limit=limit,
            rule_type=rule_type,
            is_active=is_active,
        )

    def get_pricing_rule(self, *, rule_id: int):
        rule = self.repository.get_pricing_rule(rule_id)
        if not rule:
            raise DynamicPricingApiDomainError(404, "Правило не найдено")
        return rule

    def update_pricing_rule(self, *, rule_id: int, payload: dict[str, Any]):
        rule = self.get_pricing_rule(rule_id=rule_id)
        for field, value in payload.items():
            setattr(rule, field, value)
        self.repository.commit()
        self.repository.refresh(rule)
        return rule

    def delete_pricing_rule(self, *, rule_id: int) -> dict[str, str]:
        rule = self.get_pricing_rule(rule_id=rule_id)
        self.repository.delete(rule)
        self.repository.commit()
        return {"message": "Правило удалено"}

    def calculate_price(
        self,
        *,
        services: list[dict[str, Any]],
        patient_id: int | None,
        appointment_time: datetime | None,
    ) -> dict[str, Any]:
        return self.pricing_service.apply_pricing_rules(
            services=services,
            patient_id=patient_id,
            appointment_time=appointment_time,
        )

    def create_service_package(self, *, payload: dict[str, Any], current_user_id: int):
        return self.pricing_service.create_service_package(
            name=payload["name"],
            description=payload.get("description"),
            service_ids=payload["service_ids"],
            package_price=payload["package_price"],
            valid_from=payload.get("valid_from"),
            valid_to=payload.get("valid_to"),
            max_purchases=payload.get("max_purchases"),
            per_patient_limit=payload.get("per_patient_limit"),
            created_by=current_user_id,
        )

    def list_service_packages(
        self,
        *,
        skip: int,
        limit: int,
        is_active: bool | None,
        patient_id: int | None,
    ):
        if patient_id:
            return self.pricing_service.get_available_packages(patient_id=patient_id)
        return self.repository.list_service_packages(skip=skip, limit=limit, is_active=is_active)

    def get_service_package(self, *, package_id: int):
        package = self.repository.get_service_package(package_id)
        if not package:
            raise DynamicPricingApiDomainError(404, "Пакет не найден")
        return package

    def update_service_package(self, *, package_id: int, payload: dict[str, Any]):
        package = self.get_service_package(package_id=package_id)
        if "package_price" in payload and package.original_price:
            new_price = payload["package_price"]
            package.savings_amount = package.original_price - new_price
            package.savings_percentage = (
                (package.savings_amount / package.original_price * 100)
                if package.original_price > 0
                else 0
            )
        for field, value in payload.items():
            setattr(package, field, value)
        self.repository.commit()
        self.repository.refresh(package)
        return package

    def delete_service_package(self, *, package_id: int) -> dict[str, str]:
        package = self.get_service_package(package_id=package_id)
        self.repository.delete(package)
        self.repository.commit()
        return {"message": "Пакет удален"}

    def purchase_package(
        self,
        *,
        package_id: int,
        patient_id: int,
        visit_id: int | None,
        appointment_id: int | None,
    ):
        return self.pricing_service.purchase_package(
            package_id=package_id,
            patient_id=patient_id,
            visit_id=visit_id,
            appointment_id=appointment_id,
        )

    def update_dynamic_prices(self):
        return self.pricing_service.update_dynamic_prices()

    def get_pricing_analytics(
        self,
        *,
        start_date: datetime | None,
        end_date: datetime | None,
    ):
        return self.pricing_service.get_pricing_analytics(
            start_date=start_date,
            end_date=end_date,
        )

    def get_price_history(self, *, service_id: int, skip: int, limit: int):
        history = self.repository.list_price_history(
            service_id=service_id,
            skip=skip,
            limit=limit,
        )
        return [
            {
                "id": item.id,
                "service_id": item.service_id,
                "old_price": item.old_price,
                "new_price": item.new_price,
                "price_type": item.price_type,
                "change_reason": item.change_reason,
                "change_type": item.change_type,
                "changed_at": item.changed_at,
                "changed_by": item.changed_by,
                "effective_from": item.effective_from,
                "effective_to": item.effective_to,
            }
            for item in history
        ]

    def rollback(self) -> None:
        self.repository.rollback()

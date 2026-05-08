from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.dynamic_pricing_endpoint_service import (
    DynamicPricingDomainError,
    DynamicPricingEndpointService,
)


@pytest.mark.unit
class TestDynamicPricingEndpointService:
    def test_get_pricing_rule_raises_when_missing(self):
        class Repository:
            def get_pricing_rule(self, rule_id):
                return None

        service = DynamicPricingEndpointService(
            db=None,
            repository=Repository(),
            pricing_service=None,
        )

        with pytest.raises(DynamicPricingDomainError) as exc_info:
            service.get_pricing_rule(rule_id=1)
        assert exc_info.value.status_code == 404

    def test_update_service_package_recalculates_savings(self):
        package = SimpleNamespace(
            original_price=1000.0,
            savings_amount=0.0,
            savings_percentage=0.0,
            package_price=900.0,
        )
        state = {"committed": False, "refreshed": False}

        class Repository:
            def get_service_package(self, package_id):
                return package

            def commit(self):
                state["committed"] = True

            def refresh(self, obj):
                state["refreshed"] = True

        service = DynamicPricingEndpointService(
            db=None,
            repository=Repository(),
            pricing_service=None,
        )
        updated = service.update_service_package(
            package_id=1,
            payload={"package_price": 800.0},
        )

        assert updated.savings_amount == 200.0
        assert updated.savings_percentage == 20.0
        assert state["committed"] is True
        assert state["refreshed"] is True

    def test_list_service_packages_uses_domain_service_for_patient(self):
        class PricingService:
            def get_available_packages(self, patient_id):
                return [SimpleNamespace(id=patient_id)]

        class Repository:
            def list_service_packages(self, *, skip, limit, is_active):
                raise AssertionError("repository path should not be used")

        service = DynamicPricingEndpointService(
            db=None,
            repository=Repository(),
            pricing_service=PricingService(),
        )
        result = service.list_service_packages(
            skip=0,
            limit=10,
            is_active=True,
            patient_id=3,
        )
        assert result[0].id == 3

    def test_delete_pricing_rule_cleans_linked_rows_before_delete(self):
        rule = SimpleNamespace(id=42)
        calls = []

        class Repository:
            def get_pricing_rule(self, rule_id):
                calls.append(("get", rule_id))
                return rule

            def delete_pricing_rule_dependencies(self, *, rule):
                calls.append(("cleanup", rule.id))

            def delete_pricing_rule_by_id(self, *, rule_id):
                calls.append(("delete", rule_id))

            def commit(self):
                calls.append(("commit", None))

        service = DynamicPricingEndpointService(
            db=None,
            repository=Repository(),
            pricing_service=None,
        )

        result = service.delete_pricing_rule(rule_id=42)

        assert result == {"message": "Правило удалено"}
        assert calls == [
            ("get", 42),
            ("cleanup", 42),
            ("delete", 42),
            ("commit", None),
        ]

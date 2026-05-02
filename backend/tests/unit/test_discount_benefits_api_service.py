from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace

import pytest

from app.services.discount_benefits_api_service import (
    DiscountBenefitsApiDomainError,
    DiscountBenefitsApiService,
)


@pytest.mark.unit
class TestDiscountBenefitsApiService:
    def test_get_discounts_uses_existing_domain_service_for_active_only(self):
        class DiscountService:
            def get_active_discounts(self, service_ids):
                return ["active"]

        class Repository:
            def list_all_discounts(self):
                return ["all"]

        service = DiscountBenefitsApiService(
            db=None,
            repository=Repository(),
            discount_service=DiscountService(),
        )

        assert service.get_discounts(active_only=True, service_ids=[1]) == ["active"]
        assert service.get_discounts(active_only=False, service_ids=[1]) == ["all"]

    def test_update_discount_raises_when_missing(self):
        class Repository:
            def get_discount(self, discount_id):
                return None

            def commit(self):
                raise AssertionError("commit must not be called")

        service = DiscountBenefitsApiService(db=None, repository=Repository(), discount_service=None)

        with pytest.raises(DiscountBenefitsApiDomainError) as exc_info:
            service.update_discount(discount_id=1, update_data={"name": "new"})

        assert exc_info.value.status_code == 404

    def test_delete_discount_marks_inactive_and_commits(self):
        discount = SimpleNamespace(is_active=True, updated_at=None)

        class Repository:
            committed = False

            def get_discount(self, discount_id):
                return discount

            def commit(self):
                self.committed = True

        repository = Repository()
        service = DiscountBenefitsApiService(db=None, repository=repository, discount_service=None)

        service.delete_discount(discount_id=1)

        assert discount.is_active is False
        assert isinstance(discount.updated_at, datetime)
        assert repository.committed is True

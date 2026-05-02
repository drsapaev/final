from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.derma_api_service import DermaApiDomainError, DermaApiService


@pytest.mark.unit
class TestDermaApiService:
    def test_create_price_override_rejects_non_dermatologist(self):
        class Repository:
            def get_visit(self, visit_id):
                return SimpleNamespace(id=visit_id)

            def get_service(self, service_id):
                return SimpleNamespace(
                    id=service_id,
                    allow_doctor_price_override=True,
                    price=Decimal("120"),
                )

            def get_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=8, specialty="cardiology")

        service = DermaApiService(db=None, repository=Repository())

        with pytest.raises(DermaApiDomainError) as exc_info:
            service.create_price_override(
                override_data=SimpleNamespace(
                    visit_id=1,
                    service_id=2,
                    new_price=Decimal("99"),
                    reason="manual",
                    details=None,
                ),
                user_id=10,
            )

        assert exc_info.value.status_code == 403

    def test_create_price_override_returns_created_entity(self):
        created = SimpleNamespace(id=55, visit_id=1, service_id=2)

        class Repository:
            def get_visit(self, visit_id):
                return SimpleNamespace(id=visit_id)

            def get_service(self, service_id):
                return SimpleNamespace(
                    id=service_id,
                    allow_doctor_price_override=True,
                    price=Decimal("120"),
                )

            def get_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, specialty="dermatology")

            def create_price_override(self, **kwargs):
                return created

        service = DermaApiService(db=None, repository=Repository())
        result = service.create_price_override(
            override_data=SimpleNamespace(
                visit_id=1,
                service_id=2,
                new_price=Decimal("100"),
                reason="manual",
                details="details",
            ),
            user_id=10,
        )

        assert result is created

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.services.dental_api_service import DentalApiDomainError, DentalApiService


@pytest.mark.unit
class TestDentalApiService:
    @pytest.mark.asyncio
    async def test_create_dental_price_override_raises_when_visit_missing(self):
        class Repository:
            def get_visit(self, visit_id):
                return None

        service = DentalApiService(db=None, repository=Repository())
        with pytest.raises(DentalApiDomainError) as exc_info:
            await service.create_dental_price_override(
                override_data=SimpleNamespace(
                    visit_id=1,
                    service_id=2,
                    new_price=100,
                    reason="reason",
                    details=None,
                ),
                user=SimpleNamespace(id=5),
            )
        assert exc_info.value.status_code == 404

    def test_get_dental_price_overrides_raises_when_doctor_missing(self):
        class Repository:
            def get_doctor_by_user_id(self, user_id):
                return None

        service = DentalApiService(db=None, repository=Repository())
        with pytest.raises(DentalApiDomainError) as exc_info:
            service.get_dental_price_overrides(
                user_id=7,
                visit_id=None,
                status=None,
                limit=10,
            )
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_approve_price_override_requires_rejection_reason(self):
        override = SimpleNamespace(
            status="pending",
            approved_by=None,
            approved_at=None,
            rejection_reason=None,
            visit_id=1,
            service_id=2,
        )

        class Repository:
            def get_price_override(self, override_id):
                return override

        service = DentalApiService(db=None, repository=Repository())
        with pytest.raises(DentalApiDomainError) as exc_info:
            await service.approve_price_override(
                override_id=1,
                approval_data=SimpleNamespace(action="reject", rejection_reason=None),
                user=SimpleNamespace(id=9, username="admin", full_name="Admin"),
            )
        assert exc_info.value.status_code == 400

from __future__ import annotations

from decimal import Decimal
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

    @pytest.mark.asyncio
    async def test_create_dental_price_override_rejects_foreign_visit(self):
        class Repository:
            def get_visit(self, visit_id):
                return SimpleNamespace(id=visit_id, doctor_id=99)

            def get_service(self, service_id):
                return SimpleNamespace(
                    id=service_id,
                    allow_doctor_price_override=True,
                    price=Decimal("120"),
                )

            def get_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, specialty="dental")

            def get_doctor(self, doctor_id):
                return None

        service = DentalApiService(db=None, repository=Repository())
        with pytest.raises(DentalApiDomainError) as exc_info:
            await service.create_dental_price_override(
                override_data=SimpleNamespace(
                    visit_id=1,
                    service_id=2,
                    new_price=Decimal("100"),
                    reason="reason",
                    details=None,
                ),
                user=SimpleNamespace(id=10),
            )

        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_dental_price_override_accepts_owned_visit(self):
        class Repository:
            def get_visit(self, visit_id):
                return SimpleNamespace(id=visit_id, patient_id=20, doctor_id=7)

            def get_service(self, service_id):
                return SimpleNamespace(
                    id=service_id,
                    allow_doctor_price_override=True,
                    price=Decimal("120"),
                )

            def get_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, specialty="dental", user=None)

            def get_doctor(self, doctor_id):
                return None

            def add(self, obj):
                self.created = obj

            def commit(self):
                pass

            def refresh(self, obj):
                obj.id = 55

            def list_registrars(self):
                return []

        repository = Repository()
        service = DentalApiService(db=None, repository=repository)

        result = await service.create_dental_price_override(
            override_data=SimpleNamespace(
                visit_id=1,
                service_id=2,
                new_price=Decimal("100"),
                reason="reason",
                details=None,
            ),
            user=SimpleNamespace(id=10),
        )

        assert result is repository.created
        assert result.doctor_id == 7

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

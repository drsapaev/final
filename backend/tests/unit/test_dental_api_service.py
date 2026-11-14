from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

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
    @pytest.mark.parametrize("specialty", ["stomatology", "dental", "dentistry"])
    async def test_create_dental_price_override_accepts_all_dental_specialty_vocabularies(
        self, specialty
    ):
        """Every dental specialty spelling provisioned by the system passes.

        'dentistry' is what user provisioning (user_mgmt/_core.py) and
        dev_seed actually write into doctors.specialty for dentists — it must
        not be rejected by the dental-only guard.
        """

        class Repository:
            def get_visit(self, visit_id):
                return SimpleNamespace(id=visit_id, patient_id=20, doctor_id=7)

            def get_service(self, service_id):
                return SimpleNamespace(
                    id=service_id,
                    allow_doctor_price_override=True,
                    price=Decimal("120"),
                )

            def get_visit_service(self, *, visit_id, service_id):
                return SimpleNamespace(visit_id=visit_id, service_id=service_id, price=Decimal("120"))

            def has_pending_override(self, *, visit_id, service_id):
                return False  # REGPRICE-BE-003: no other pending intent

            def get_doctor_by_user_id(self, user_id):
                return SimpleNamespace(id=7, specialty=specialty, user=None)

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
        assert result is not None
        assert repository.created.doctor_id == 7

    @pytest.mark.asyncio
    async def test_create_dental_price_override_rejects_non_dental_specialty(self):
        """A non-dental doctor must still be rejected (403)."""

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
                return SimpleNamespace(id=7, specialty="cardiology", user=None)

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

            def get_visit_service(self, *, visit_id, service_id):
                return SimpleNamespace(visit_id=visit_id, service_id=service_id, price=Decimal("120"))

            def has_pending_override(self, *, visit_id, service_id):
                return False  # REGPRICE-BE-003: no other pending intent

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

    @pytest.mark.asyncio
    async def test_price_override_pending_uses_protected_inbox_and_tracks_delivery(
        self, monkeypatch
    ):
        import app.services.dental_api_service as dental_module

        registrars = [
            SimpleNamespace(id=31, username="registrar-one", is_active=True),
            SimpleNamespace(id=32, username="registrar-two", is_active=True),
        ]

        class Repository:
            commits = 0

            def list_registrars(self):
                return registrars

            def commit(self):
                self.commits += 1

        repository = Repository()
        service = DentalApiService(db=object(), repository=repository)
        notification = AsyncMock(side_effect=[False, True])
        monkeypatch.setattr(
            dental_module.notification_sender_service,
            "send_canonical_notification_to_user",
            notification,
        )
        override = SimpleNamespace(
            id=90,
            visit_id=7,
            service_id=4,
            original_price=Decimal("120"),
            new_price=Decimal("100"),
            reason="synthetic test",
            details=None,
            created_at=datetime(2026, 11, 14, 10, 0),
            notification_sent=False,
            notification_sent_at=None,
        )

        await service.send_price_override_notification(
            price_override=override,
            doctor=SimpleNamespace(
                id=12,
                user=SimpleNamespace(full_name="Synthetic Doctor"),
            ),
            service=SimpleNamespace(name="Synthetic service", service_code="SVC-4"),
            visit=SimpleNamespace(patient_id=22),
        )

        assert notification.await_count == 2
        assert [call.kwargs["recipient"] for call in notification.await_args_list] == (
            registrars
        )
        assert all(
            call.kwargs["source_module"] == "dental"
            for call in notification.await_args_list
        )
        assert override.notification_sent is True
        assert override.notification_sent_at is not None
        assert repository.commits == 1

    @pytest.mark.asyncio
    async def test_price_override_result_uses_doctor_protected_inbox(
        self, monkeypatch
    ):
        import app.services.dental_api_service as dental_module

        doctor_user = SimpleNamespace(
            id=12,
            username="synthetic-doctor",
            full_name="Synthetic Doctor",
            is_active=True,
        )

        class Repository:
            def get_doctor(self, doctor_id):
                return SimpleNamespace(user=doctor_user)

            def get_service(self, service_id):
                return SimpleNamespace(name="Synthetic service")

        service = DentalApiService(db=object(), repository=Repository())
        notification = AsyncMock(return_value=True)
        telegram = AsyncMock()
        monkeypatch.setattr(
            dental_module.notification_sender_service,
            "send_canonical_notification_to_user",
            notification,
        )
        monkeypatch.setattr(
            dental_module.notification_sender_service,
            "send_telegram_message",
            telegram,
        )

        await service.send_price_override_result_notification(
            price_override=SimpleNamespace(
                id=90,
                doctor_id=12,
                service_id=4,
                visit_id=7,
                status="approved",
                original_price=Decimal("120"),
                new_price=Decimal("100"),
                reason="synthetic test",
                approved_at=datetime(2026, 11, 14, 10, 0),
                rejection_reason=None,
            ),
            approved_by=SimpleNamespace(username="admin", full_name="Synthetic Admin"),
        )

        notification.assert_awaited_once()
        assert notification.await_args.kwargs["recipient"] is doctor_user
        assert notification.await_args.kwargs["event_type"] == "dental_price_override_result"
        assert notification.await_args.kwargs["source_module"] == "dental"
        telegram.assert_not_awaited()

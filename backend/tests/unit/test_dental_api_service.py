from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.services.dental_api_service import DentalApiDomainError, DentalApiService
from tests.unit.test_derma_api_service import Repository, _bearer, _data


@pytest.mark.unit
class TestDentalApiService:
    @pytest.mark.asyncio
    async def test_create_dental_price_override_raises_when_visit_missing(self):
        repo = Repository()
        repo.doctor.specialty = "dental"
        repo.visit = None
        with pytest.raises(DentalApiDomainError) as exc:
            await DentalApiService(None, repo).create_dental_price_override(override_data=_data(), user=repo.actor, bearer=_bearer())
        assert exc.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_dental_price_override_rejects_foreign_visit(self):
        repo = Repository()
        repo.doctor.specialty = "dental"
        repo.visit.doctor_id = 99
        with pytest.raises(DentalApiDomainError) as exc:
            await DentalApiService(None, repo).create_dental_price_override(override_data=_data(), user=repo.actor, bearer=_bearer())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    @pytest.mark.parametrize("specialty", ["stomatology", "dental", "dentistry"])
    async def test_create_dental_price_override_accepts_all_dental_specialty_vocabularies(self, specialty):
        repo = Repository()
        repo.doctor.specialty = specialty
        repo.add = lambda obj: setattr(repo, "created", obj)
        repo.flush = lambda: None
        repo.commit_request = lambda context: None
        repo.refresh = lambda obj: None
        service = DentalApiService(None, repo)
        service.send_price_override_notification = AsyncMock()
        result = await service.create_dental_price_override(override_data=_data(), user=repo.actor, bearer=_bearer())
        assert result is not repo.created
        assert result.doctor_id == 7
        assert result.target_visit_service_id == 3
        assert result.visit_context_epoch == 9
        assert result.doctor_owner_generation == 8
        assert (result.price_context_generation, result.price_line_generation,
                result.price_owner_generation, result.requester_auth_epoch) == (13, 14, 12, 4)
        assert result.requester_type == "doctor" and result.requester_user_id_snapshot == 10

    @pytest.mark.asyncio
    async def test_user_id_is_not_an_assigned_doctor(self):
        repo = Repository()
        repo.doctor.specialty = "dental"
        repo.visit.doctor_id = repo.actor.id
        with pytest.raises(DentalApiDomainError) as exc:
            await DentalApiService(None, repo).create_dental_price_override(override_data=_data(), user=repo.actor, bearer=_bearer())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_dental_price_override_rejects_non_dental_specialty(self):
        repo = Repository()
        repo.doctor.specialty = "cardiology"
        with pytest.raises(DentalApiDomainError) as exc:
            await DentalApiService(None, repo).create_dental_price_override(override_data=_data(), user=repo.actor, bearer=_bearer())
        assert exc.value.status_code == 403

    @pytest.mark.asyncio
    async def test_create_dental_price_override_accepts_owned_visit(self):
        repo = Repository()
        repo.doctor.specialty = "dental"
        repo.add = lambda obj: setattr(repo, "created", obj)
        repo.flush = lambda: None
        repo.commit_request = lambda context: None
        repo.refresh = lambda obj: None
        service = DentalApiService(None, repo)
        service.send_price_override_notification = AsyncMock()
        result = await service.create_dental_price_override(override_data=_data(), user=repo.actor, bearer=_bearer())
        assert result is not repo.created
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
                bearer=None,
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
    @pytest.mark.parametrize("binding", ["current", "reassigned", "rebound", "revoked"])
    async def test_price_override_result_uses_doctor_protected_inbox(
        self, monkeypatch, binding
    ):
        import app.services.dental_api_service as dental_module

        doctor_user = SimpleNamespace(
            id=14 if binding == "reassigned" else 12,
            username="synthetic-doctor",
            full_name="Synthetic Doctor",
            is_active=True,
            role="dentist",
            auth_epoch=2 if binding == "revoked" else 1,
        )

        class Repository:
            def get_doctor(self, doctor_id):
                return SimpleNamespace(
                    user=doctor_user,
                    active=True,
                    repeat_owner_generation=5 if binding == "rebound" else 4,
                    price_owner_generation=8,
                )

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
                doctor_owner_user_id=12,
                doctor_owner_generation=4,
                price_owner_generation=8,
                doctor_user_auth_epoch=1,
            ),
        )

        if binding == "current":
            notification.assert_awaited_once()
            sent = notification.await_args.kwargs
            assert sent["recipient"] is doctor_user
            assert sent["event_type"] == "dental_price_override_result"
            assert sent["source_module"] == "dental"
            assert sent["metadata"] == {"override_id": 90, "status": "approved"}
            assert sent["message"] == "Решение доступно в списке изменений цены."
        else:
            notification.assert_not_awaited()
        telegram.assert_not_awaited()

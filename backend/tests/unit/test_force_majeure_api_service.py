from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace

import pytest

from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)


@pytest.mark.unit
class TestForceMajeureApiService:
    def test_cancel_queue_with_refund_rejects_invalid_type(self, monkeypatch):
        monkeypatch.setattr(
            "app.services.force_majeure_api_service.get_force_majeure_service",
            lambda db: SimpleNamespace(),
        )

        repository = SimpleNamespace(db=None)
        service = ForceMajeureApiService(db=None, repository=repository)

        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.cancel_queue_with_refund(
                request=SimpleNamespace(
                    refund_type="bad",
                    entry_ids=None,
                    specialist_id=1,
                    target_date=None,
                    reason="reason",
                    send_notifications=False,
                ),
                current_user_id=10,
            )

        assert exc_info.value.status_code == 400

    def test_process_refund_request_reject_requires_reason(self):
        request_obj = SimpleNamespace(
            status="pending",
            processed_by=None,
            processed_at=None,
            patient=None,
            processor=None,
            id=1,
            patient_id=2,
            payment_id=3,
            original_amount=Decimal("10"),
            refund_amount=Decimal("10"),
            commission_amount=Decimal("0"),
            refund_type="deposit",
            reason="r",
            is_automatic=False,
            bank_card_number=None,
            created_at=None,
        )

        class Repository:
            def get_refund_request(self, request_id):
                return request_obj

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.process_refund_request(
                request_id=1,
                process_request=SimpleNamespace(
                    action="reject",
                    rejection_reason=None,
                    bank_card_number=None,
                    manager_notes=None,
                ),
                current_user=SimpleNamespace(id=1, full_name="Admin"),
            )
        assert exc_info.value.status_code == 400

    def test_use_deposit_for_payment_checks_balance(self):
        deposit = SimpleNamespace(
            balance=Decimal("50"),
            is_active=True,
            patient=None,
            id=1,
            patient_id=2,
            currency="UZS",
            created_at=None,
        )

        class Repository:
            def get_patient_deposit(self, *, patient_id):
                return deposit

        service = ForceMajeureApiService(db=None, repository=Repository())
        with pytest.raises(ForceMajeureApiDomainError) as exc_info:
            service.use_deposit_for_payment(
                request=SimpleNamespace(
                    patient_id=2,
                    amount=100,
                    visit_id=None,
                    description=None,
                ),
                current_user_id=1,
            )
        assert exc_info.value.status_code == 400

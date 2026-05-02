from __future__ import annotations

import pytest

from app.models.payment import Payment
from app.services.payment_cancel_service import (
    PaymentCancelDomainError,
    PaymentCancelService,
)
from app.services.payment_providers.base import PaymentResult


class _FakePaymentManager:
    def __init__(self, result: PaymentResult):
        self.result = result

    def cancel_payment(self, provider_name: str, provider_payment_id: str) -> PaymentResult:
        return self.result


@pytest.mark.unit
class TestPaymentCancelService:
    def test_cancel_payment_not_found(self, db_session):
        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=False))
        )

        with pytest.raises(PaymentCancelDomainError) as exc_info:
            service.cancel_payment(payment_id=999999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Платеж не найден"

    def test_cancel_payment_rejects_non_cancellable_status(self, db_session, test_visit):
        payment = Payment(
            visit_id=test_visit.id,
            amount=10_000.0,
            currency="UZS",
            method="cash",
            status="paid",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )

        with pytest.raises(PaymentCancelDomainError) as exc_info:
            service.cancel_payment(payment_id=payment.id)

        assert exc_info.value.status_code == 400
        assert "нельзя отменить" in exc_info.value.detail

    def test_cancel_cash_payment(self, db_session, test_visit):
        payment = Payment(
            visit_id=test_visit.id,
            amount=10_000.0,
            currency="UZS",
            method="cash",
            status="pending",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentCancelService(
            db_session, _FakePaymentManager(PaymentResult(success=True))
        )
        result = service.cancel_payment(payment_id=payment.id)

        db_session.refresh(payment)
        assert result["success"] is True
        assert payment.status == "cancelled"

    def test_cancel_online_payment_provider_failure_still_cancels(
        self, db_session, test_visit
    ):
        payment = Payment(
            visit_id=test_visit.id,
            amount=10_000.0,
            currency="UZS",
            method="online",
            status="processing",
            provider="click",
            provider_payment_id="provider-123",
            provider_data={"source": "unit"},
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentCancelService(
            db_session,
            _FakePaymentManager(
                PaymentResult(success=False, error_message="provider unavailable")
            ),
        )
        service.cancel_payment(payment_id=payment.id)

        db_session.refresh(payment)
        assert payment.status == "cancelled"
        assert payment.provider_data["source"] == "unit"

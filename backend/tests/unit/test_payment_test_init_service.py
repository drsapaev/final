from __future__ import annotations

import pytest

from app.models.payment import Payment
from app.services.payment_providers.base import PaymentResult
from app.services.payment_test_init_service import (
    PaymentTestInitDomainError,
    PaymentTestInitService,
)


class _FakePaymentManager:
    def __init__(self, result: PaymentResult):
        self.result = result

    def create_payment(self, **kwargs) -> PaymentResult:  # type: ignore[no-untyped-def]
        return self.result


@pytest.mark.unit
class TestPaymentTestInitService:
    def test_init_test_payment_success(self, db_session, test_visit):
        service = PaymentTestInitService(
            db_session,
            _FakePaymentManager(
                PaymentResult(
                    success=True,
                    payment_id="provider-1",
                    payment_url="https://pay.example/checkout",
                )
            ),
        )

        result = service.init_test_payment(
            visit_id=test_visit.id,
            provider="click",
            amount=20_000.0,
            currency="UZS",
            description="test",
            return_url=None,
            cancel_url=None,
        )

        payment = (
            db_session.query(Payment)
            .filter(Payment.id == result["payment_id"])
            .first()
        )
        assert payment is not None
        assert payment.status == "processing"
        assert payment.provider_payment_id == "provider-1"
        assert result["success"] is True

    def test_init_test_payment_provider_failure(self, db_session, test_visit):
        service = PaymentTestInitService(
            db_session,
            _FakePaymentManager(
                PaymentResult(success=False, error_message="provider unavailable")
            ),
        )

        with pytest.raises(PaymentTestInitDomainError) as exc_info:
            service.init_test_payment(
                visit_id=test_visit.id,
                provider="click",
                amount=20_000.0,
                currency="UZS",
                description=None,
                return_url=None,
                cancel_url=None,
            )

        assert exc_info.value.status_code == 400
        assert "provider unavailable" in exc_info.value.detail

        payment = db_session.query(Payment).order_by(Payment.id.desc()).first()
        assert payment is not None
        assert payment.status == "failed"

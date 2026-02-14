from __future__ import annotations

from unittest.mock import Mock, patch

import pytest

from app.models.payment import Payment
from app.services.payment_init_service import PaymentInitDomainError, PaymentInitService
from app.services.payment_providers.base import PaymentResult


class _FakeManager:
    def __init__(self, *, providers: list[str], result: PaymentResult | None = None):
        self._providers = providers
        self._result = result or PaymentResult(success=False, error_message="no result")

    def get_providers_for_currency(self, currency: str) -> list[str]:
        return self._providers

    def create_payment(self, **kwargs) -> PaymentResult:  # type: ignore[no-untyped-def]
        return self._result


@pytest.mark.unit
class TestPaymentInitService:
    @patch("app.services.payment_init_service.log_critical_change")
    def test_init_payment_visit_not_found(self, _audit_mock, db_session, admin_user):
        service = PaymentInitService(db_session, _FakeManager(providers=["click"]))

        with pytest.raises(PaymentInitDomainError) as exc_info:
            service.init_payment(
                request=Mock(),
                current_user_id=admin_user.id,
                visit_id=999999,
                provider="click",
                amount=100000.0,
                currency="UZS",
                description=None,
                return_url=None,
                cancel_url=None,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Визит не найден"

    @patch("app.services.payment_init_service.log_critical_change")
    def test_init_payment_provider_not_supported(self, _audit_mock, db_session, admin_user, test_visit):
        service = PaymentInitService(db_session, _FakeManager(providers=[]))

        result = service.init_payment(
            request=Mock(),
            current_user_id=admin_user.id,
            visit_id=test_visit.id,
            provider="click",
            amount=100000.0,
            currency="UZS",
            description=None,
            return_url=None,
            cancel_url=None,
        )

        assert result["success"] is False
        assert "не поддерживает валюту" in result["error_message"]

    @patch("app.services.payment_init_service.log_critical_change")
    def test_init_payment_success(self, _audit_mock, db_session, admin_user, test_visit):
        manager = _FakeManager(
            providers=["click"],
            result=PaymentResult(
                success=True,
                payment_id="provider_123",
                status="pending",
                payment_url="https://pay.example/checkout",
                provider_data={"gateway": "click"},
            ),
        )
        service = PaymentInitService(db_session, manager)

        result = service.init_payment(
            request=Mock(),
            current_user_id=admin_user.id,
            visit_id=test_visit.id,
            provider="click",
            amount=100000.0,
            currency="UZS",
            description="test init",
            return_url=None,
            cancel_url=None,
        )

        assert result["success"] is True
        payment_id = result["payment_id"]
        assert payment_id is not None

        payment = db_session.query(Payment).filter(Payment.id == payment_id).first()
        assert payment is not None
        assert payment.provider == "click"
        assert payment.provider_payment_id == "provider_123"
        assert payment.payment_url == "https://pay.example/checkout"

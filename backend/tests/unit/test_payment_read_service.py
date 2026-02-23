from __future__ import annotations

import pytest

from app.models.payment import Payment
from app.services.payment_providers.base import PaymentResult
from app.services.payment_read_service import PaymentReadDomainError, PaymentReadService


class _FakePaymentManager:
    def __init__(self, result: PaymentResult):
        self.result = result

    def check_payment_status(self, provider_name: str, provider_payment_id: str) -> PaymentResult:
        return self.result


@pytest.mark.unit
class TestPaymentReadService:
    def test_get_payment_status_not_found(self, db_session):
        service = PaymentReadService(
            db_session, _FakePaymentManager(PaymentResult(success=True, status="paid"))
        )

        with pytest.raises(PaymentReadDomainError) as exc_info:
            service.get_payment_status(payment_id=999999)

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Платеж не найден"

    def test_get_payment_status_syncs_with_provider(self, db_session, test_visit):
        payment = Payment(
            visit_id=test_visit.id,
            amount=15_000.0,
            currency="UZS",
            method="online",
            status="pending",
            provider="click",
            provider_payment_id="provider-123",
            provider_data={"source": "unit"},
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentReadService(
            db_session,
            _FakePaymentManager(
                PaymentResult(success=True, status="paid", provider_data={"synced": True})
            ),
        )
        result = service.get_payment_status(payment_id=payment.id)

        db_session.refresh(payment)
        assert payment.status == "paid"
        assert payment.provider_data["source"] == "unit"
        assert result["status"] == "paid"
        assert result["payment_id"] == payment.id

    def test_get_visit_payments_returns_formatted_items(self, db_session, test_visit):
        payment_1 = Payment(
            visit_id=test_visit.id,
            amount=10_000.0,
            currency="UZS",
            method="cash",
            status="paid",
        )
        payment_2 = Payment(
            visit_id=test_visit.id,
            amount=5_000.0,
            currency="UZS",
            method="card",
            status="pending",
        )
        db_session.add(payment_1)
        db_session.add(payment_2)
        db_session.commit()

        service = PaymentReadService(db_session)
        result = service.get_visit_payments(visit_id=test_visit.id)

        assert result["total"] == 2
        returned_ids = {item["payment_id"] for item in result["payments"]}
        assert returned_ids == {payment_1.id, payment_2.id}

    def test_generate_receipt_not_found(self, db_session):
        service = PaymentReadService(db_session)

        with pytest.raises(PaymentReadDomainError) as exc_info:
            service.generate_receipt(payment_id=999999, format_type="pdf")

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Платеж не найден"

    def test_generate_receipt_success(self, db_session, test_visit):
        payment = Payment(
            visit_id=test_visit.id,
            amount=8_000.0,
            currency="UZS",
            method="cash",
            status="paid",
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentReadService(db_session)
        result = service.generate_receipt(payment_id=payment.id, format_type="pdf")

        assert result["success"] is True
        assert result["receipt_data"]["payment_id"] == payment.id
        assert result["format"] == "pdf"

    def test_build_receipt_content_allows_missing_provider(self, db_session, test_visit):
        payment = Payment(
            visit_id=test_visit.id,
            amount=8_000.0,
            currency="UZS",
            method="cash",
            status="paid",
            provider=None,
        )
        db_session.add(payment)
        db_session.commit()
        db_session.refresh(payment)

        service = PaymentReadService(db_session)
        content = service.build_receipt_content(payment_id=payment.id)

        assert f"Номер платежа: {payment.id}" in content
        assert "Провайдер: —" in content

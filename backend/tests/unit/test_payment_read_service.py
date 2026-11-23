from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError

from app.models.audit import AuditLog
from app.models.payment import Payment
from app.services.payment_providers.base import PaymentResult
from app.services.payment_providers.click import ClickProvider
from app.services.payment_read_service import PaymentReadDomainError, PaymentReadService


class _FakePaymentManager:
    def __init__(self, result: PaymentResult):
        self.result = result

    def check_payment_status(self, provider_name: str, provider_payment_id: str) -> PaymentResult:
        return self.result


def _provider_transitions(db_session, payment_id):
    return db_session.scalars(
        select(AuditLog).filter_by(
            event_type="PAYMENT_PROVIDER_STATUS_CHANGED", entity_type="payment", entity_id=payment_id,
        )
    ).all()


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
        assert payment.provider_data == {"source": "unit", "synced": True}
        assert result["status"] == "paid"
        assert result["payment_id"] == payment.id
        assert result["provider_data"] == payment.provider_data
        (transition,) = _provider_transitions(db_session, payment.id)
        assert transition.action == "payment_provider_status_changed"
        assert transition.actor_type == "system"
        assert transition.actor_user_id is None
        assert transition.resource_type == "payment"
        assert transition.resource_id == str(payment.id)
        assert transition.outcome == "success"
        assert transition.payload == {
            "previous_status": "pending",
            "new_status": "paid",
            "amount": "15000.00",
            "currency": "UZS",
            "provider": "click",
        }

    def test_provider_poll_rolls_back_if_audit_write_fails(self, db_session, test_visit, monkeypatch):
        order_id = "SYNTHETIC-audit"
        payment = Payment(
            visit_id=test_visit.id, amount=Decimal("7350.25"), currency="UZS",
            method="online", status="pending", provider="click", provider_payment_id=order_id,
            provider_data={"recorded": True},
        )
        db_session.add(payment)
        db_session.commit()
        payment_id = payment.id
        service = PaymentReadService(db_session, _FakePaymentManager(PaymentResult(
            success=True, payment_id=order_id, status="paid",
            provider_data={"merchant_trans_id": order_id, "amount": "7350.25"},
        )))

        def fail_audit(pending_payment, *, previous_status):
            assert previous_status == "pending"
            assert pending_payment.status == "paid" and pending_payment.paid_at is not None
            raise SQLAlchemyError("SYNTHETIC-storage-error")

        monkeypatch.setattr(service.repository, "record_provider_transition", fail_audit)

        with pytest.raises(PaymentReadDomainError) as error:
            service.get_payment_status(payment_id=payment_id)

        assert error.value.status_code == 503
        assert error.value.detail == "Обновление статуса платежа временно недоступно"
        db_session.refresh(payment)
        assert payment.status == "pending" and payment.paid_at is None
        assert payment.provider_data == {"recorded": True}
        assert _provider_transitions(db_session, payment_id) == []

    def test_provider_poll_preserves_payment_posted_during_lookup(self, db_session, test_visit):
        payment = Payment(
            visit_id=test_visit.id,
            amount=Decimal("15000.00"),
            currency="UZS",
            method="online",
            status="pending",
            provider="click",
            provider_payment_id="SYNTHETIC-status-read",
        )
        db_session.add(payment)
        db_session.commit()
        payment_id = payment.id
        posting_time = datetime(2026, 1, 10, 12, tzinfo=UTC)

        def check_payment_status(provider, order_id):
            assert provider == "click"
            assert order_id == "SYNTHETIC-status-read"
            # Apply the authoritative database change without updating the cached ORM row.
            db_session.connection().execute(
                update(Payment)
                .where(Payment.id == payment_id)
                .values(status="paid", paid_at=posting_time, provider_data={"source": "SYNTHETIC-settlement"})
            )
            return PaymentResult(success=True, status="processing", provider_data={"status": 1})

        manager = Mock()
        manager.check_payment_status.side_effect = check_payment_status
        result = PaymentReadService(db_session, manager).get_payment_status(payment_id=payment_id)

        db_session.refresh(payment)
        assert result["status"] == payment.status == "paid"
        assert payment.paid_at is not None
        assert payment.paid_at.replace(tzinfo=payment.paid_at.tzinfo or UTC) == posting_time
        assert payment.provider_data == {"source": "SYNTHETIC-settlement"}
        assert _provider_transitions(db_session, payment_id) == []

    def test_provider_poll_reports_saved_status_for_disallowed_transition(self, db_session, test_visit):
        payment = Payment(
            visit_id=test_visit.id,
            amount=Decimal("15000.00"),
            currency="UZS",
            method="online",
            status="pending",
            provider="click",
            provider_payment_id="SYNTHETIC-incomplete-proof",
        )
        db_session.add(payment)
        db_session.commit()
        manager = _FakePaymentManager(PaymentResult(success=True, status="completed"))

        result = PaymentReadService(db_session, manager).get_payment_status(payment_id=payment.id)

        db_session.refresh(payment)
        assert result["status"] == payment.status == "pending"
        assert payment.paid_at is None
        assert payment.provider_data is None
        assert _provider_transitions(db_session, payment.id) == []

    @pytest.mark.parametrize(
        ("provider_response", "expected_status"),
        [
            pytest.param({}, "pending", id="missing-status"),
            pytest.param({"status": 99}, "pending", id="unknown-status"),
            pytest.param({"status": "-1"}, "pending", id="string-status"),
            pytest.param({"status": True}, "pending", id="boolean-status"),
            pytest.param([], "pending", id="non-object-response"),
            pytest.param({"status": 1}, "processing", id="reported-processing"),
            pytest.param({"status": -1}, "failed", id="reported-failure"),
        ],
    )
    def test_click_status_read_uses_only_known_provider_codes(
        self, db_session, test_visit, monkeypatch, provider_response, expected_status,
    ):
        payment = Payment(
            visit_id=test_visit.id,
            amount=Decimal("15000.00"),
            currency="UZS",
            method="online",
            status="pending",
            provider="click",
            provider_payment_id="synthetic-order",
        )
        db_session.add(payment)
        db_session.commit()
        provider = ClickProvider({
            "service_id": "synthetic-service",
            "merchant_id": "synthetic-merchant",
            "secret_key": "synthetic-config",
            "base_url": "https://synthetic-provider.invalid",
        })
        response = Mock()
        response.json.return_value = provider_response
        monkeypatch.setattr("app.services.payment_providers.click.httpx.post", Mock(return_value=response))

        observation = provider.check_payment_status(payment.provider_payment_id)
        service = PaymentReadService(db_session, _FakePaymentManager(observation))
        result = service.get_payment_status(payment_id=payment.id)

        db_session.refresh(payment)
        assert result["status"] == payment.status == expected_status
        assert payment.paid_at is None
        if expected_status == "pending":
            assert not observation.success
            assert payment.provider_data is None
        else:
            assert observation.success
            assert payment.provider_data == provider_response
        if expected_status == "processing":
            assert service.get_payment_status(payment_id=payment.id)["status"] == "processing"
        transitions = _provider_transitions(db_session, payment.id)
        if expected_status == "pending":
            assert transitions == []
        else:
            (transition,) = transitions
            assert transition.payload["new_status"] == expected_status

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

    def test_build_receipt_pdf_returns_pdf_bytes(self, db_session, test_visit):
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
        pdf_bytes = service.build_receipt_pdf(payment_id=payment.id)

        assert pdf_bytes.startswith(b"%PDF")
        assert len(pdf_bytes) > 500

    @pytest.mark.parametrize("currency,label", [
        ("USD", "USD"), ("UZS", "UZS"), (None, "валюта не указана"), ("usd", "валюта не указана"),
    ])
    def test_pdf_uses_payment_currency_and_exact_cents_for_refund(
        self, db_session, test_visit, monkeypatch, currency, label,
    ):
        from reportlab.pdfgen import canvas

        payment = Payment(visit_id=test_visit.id, amount=Decimal("10.25"), currency="USD", method="cash",
                          status="paid", refunded_amount=Decimal("1.75"))
        db_session.add(payment)
        db_session.commit()
        service = PaymentReadService(db_session)
        context = service._load_receipt_context(payment_id=payment.id)
        context["payment"].currency = currency
        monkeypatch.setattr(service, "_load_receipt_context", lambda **_: context)
        lines = []
        original_draw = canvas.Canvas.drawString

        def record_draw(instance, x, y, text, *args, **kwargs):
            lines.append(text)
            return original_draw(instance, x, y, text, *args, **kwargs)

        monkeypatch.setattr(canvas.Canvas, "drawString", record_draw)
        assert service.build_receipt_pdf(payment_id=payment.id).startswith(b"%PDF")
        assert f"Сумма: 10.25 {label}" in lines
        assert f"Возврат: 1.75 {label}" in lines
        assert f"Сумма: 10.25 {label}" in service.build_receipt_content(payment_id=payment.id)

    @pytest.mark.parametrize("amount", ["NaN", "1.001"])
    def test_receipt_rejects_amounts_that_cannot_be_rendered_exactly(self, amount):
        with pytest.raises(PaymentReadDomainError) as error:
            PaymentReadService._format_amount(Decimal(amount))
        assert error.value.status_code == 409

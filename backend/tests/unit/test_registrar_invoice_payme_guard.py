from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.api.v1.endpoints.registrar_wizard import _invoice as invoice_module
from app.api.v1.endpoints.registrar_wizard._helpers import InvoicePaymentRequest


@pytest.mark.unit
def test_invoice_payment_rejects_payme_before_emitting_unreconciled_link(
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = SimpleNamespace(id=42, status="pending")
    db = Mock()
    (
        db.query.return_value.filter.return_value.with_for_update.return_value.first
    ).return_value = invoice
    manager = Mock()
    manager.supports_registrar_invoice_payment.return_value = False
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    response = invoice_module.init_invoice_payment(
        payment_req=InvoicePaymentRequest(invoice_id=42, provider="payme"),
        db=db,
        current_user=Mock(),
    )

    assert response.success is False
    assert "не поддерживается" in (response.error_message or "")
    assert invoice.status == "pending"
    manager.supports_registrar_invoice_payment.assert_called_once_with("payme")
    manager.create_payment.assert_not_called()
    db.commit.assert_not_called()


@pytest.mark.unit
def test_invoice_payment_uses_click_when_manager_advertises_capability(
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = SimpleNamespace(
        id=42,
        status="pending",
        total_amount=Decimal("125000"),
        currency="UZS",
    )
    db = Mock()
    (
        db.query.return_value.filter.return_value.with_for_update.return_value.first
    ).return_value = invoice
    manager = Mock()
    manager.supports_registrar_invoice_payment.return_value = True
    manager.create_payment.return_value = SimpleNamespace(
        success=True,
        payment_id="click-payment-42",
        payment_url="https://my.click.uz/pay/42",
        provider_data={"merchant_trans_id": "invoice_42"},
    )
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    response = invoice_module.init_invoice_payment(
        payment_req=InvoicePaymentRequest(invoice_id=42, provider="CLICK"),
        db=db,
        current_user=Mock(),
    )

    assert response.success is True
    assert response.payment_url == "https://my.click.uz/pay/42"
    manager.supports_registrar_invoice_payment.assert_called_once_with("click")
    manager.create_payment.assert_called_once_with(
        provider_name="click",
        amount=Decimal("125000"),
        currency="UZS",
        order_id="invoice_42",
        description="Оплата визитов #42",
        return_url=None,
        cancel_url=None,
    )
    assert invoice.provider_payment_id == "click-payment-42"
    assert invoice.payment_method == "click"
    assert invoice.provider == "click"
    assert invoice.status == "processing"
    assert invoice.provider_data == {"merchant_trans_id": "invoice_42"}
    db.commit.assert_called_once_with()

from __future__ import annotations

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
    manager.create_payment.assert_not_called()
    db.commit.assert_not_called()

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.models.billing import InvoiceStatus
from app.services.billing_api_service import BillingApiDomainError, BillingApiService


@pytest.mark.unit
class TestBillingApiService:
    def test_delete_invoice_rejects_non_draft(self):
        invoice = SimpleNamespace(status=InvoiceStatus.PAID)

        class Repository:
            def get_invoice(self, invoice_id):
                return invoice

        service = BillingApiService(db=None, repository=Repository())

        with pytest.raises(BillingApiDomainError) as exc_info:
            service.delete_invoice(invoice_id=1)

        assert exc_info.value.status_code == 400

    def test_serialize_payments_returns_expected_payload(self):
        payment = SimpleNamespace(
            id=1,
            visit_id=2,
            amount=15.5,
            method="cash",
            status="paid",
            receipt_no="R1",
            note="ok",
            created_at="2026-01-01T00:00:00",
            paid_at="2026-01-01T00:01:00",
        )

        payload = BillingApiService.serialize_payments([payment])
        assert payload[0]["id"] == 1
        assert payload[0]["amount"] == 15.5

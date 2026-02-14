from __future__ import annotations

import pytest

from app.models.payment_invoice import PaymentInvoice
from app.services.payment_invoice_service import (
    PaymentInvoiceDomainError,
    PaymentInvoiceService,
)


@pytest.mark.unit
class TestPaymentInvoiceService:
    def test_create_invoice_success(self, db_session, admin_user):
        service = PaymentInvoiceService(db_session)
        result = service.create_invoice(
            amount=12_500.0,
            currency="UZS",
            provider="click",
            description="unit invoice",
            patient_info=None,
            created_by_id=admin_user.id,
        )

        invoice = (
            db_session.query(PaymentInvoice)
            .filter(PaymentInvoice.id == result["invoice_id"])
            .first()
        )
        assert invoice is not None
        assert invoice.patient_id == 0
        assert result["amount"] == 12_500.0
        assert result["description"] == "unit invoice"
        assert invoice.provider_data["created_by_id"] == admin_user.id

    def test_create_invoice_invalid_patient_id(self, db_session):
        service = PaymentInvoiceService(db_session)

        with pytest.raises(PaymentInvoiceDomainError) as exc_info:
            service.create_invoice(
                amount=10_000.0,
                currency="UZS",
                provider="click",
                description=None,
                patient_info={"patient_id": "bad-id"},
                created_by_id=None,
            )

        assert exc_info.value.status_code == 400
        assert "Некорректный patient_id" in exc_info.value.detail

    def test_list_pending_invoices_filters_by_status(self, db_session):
        pending_invoice = PaymentInvoice(
            patient_id=1,
            total_amount=7_000.0,
            currency="UZS",
            status="pending",
            payment_method="click",
            provider="click",
        )
        paid_invoice = PaymentInvoice(
            patient_id=1,
            total_amount=9_000.0,
            currency="UZS",
            status="paid",
            payment_method="click",
            provider="click",
        )
        db_session.add(pending_invoice)
        db_session.add(paid_invoice)
        db_session.commit()

        service = PaymentInvoiceService(db_session)
        invoices = service.list_pending_invoices(limit=50)

        ids = {invoice["invoice_id"] for invoice in invoices}
        assert pending_invoice.id in ids
        assert paid_invoice.id not in ids

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import VisitService
from app.services import payment_invoice_service as payment_invoice_service_module
from app.services.payment_invoice_service import (
    PaymentInvoiceDomainError,
    PaymentInvoiceService,
)


class _PaymentManagerStub:
    def get_provider_info(self):
        return {
            "click": {
                "supported_currencies": ["UZS"],
            },
        }

    def supports_registrar_invoice_payment(self, provider_name: str) -> bool:
        return provider_name.lower() == "click"


def _create_linked_invoice(
    db_session,
    test_visit,
    *,
    amount: int,
    service_amount: int | None = None,
    provider: str | None = None,
    payment_method: str = "cash",
) -> PaymentInvoice:
    db_session.add(
        VisitService(
            visit_id=test_visit.id,
            service_id=1,
            name="SYNTHETIC-invoice service",
            qty=1,
            price=service_amount if service_amount is not None else amount,
        )
    )
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=amount,
        currency="UZS",
        status="pending",
        payment_method=payment_method,
        provider=provider,
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=test_visit.id,
            visit_amount=amount,
        )
    )
    db_session.commit()
    return invoice


@pytest.mark.unit
class TestPaymentInvoiceService:
    def test_create_invoice_success(self, db_session, admin_user, test_patient):
        service = PaymentInvoiceService(db_session)
        result = service.create_invoice(
            amount=12_500.0,
            currency="UZS",
            provider="click",
            description="unit invoice",
            patient_id=test_patient.id,
            created_by_id=admin_user.id,
        )

        invoice = (
            db_session.query(PaymentInvoice)
            .filter(PaymentInvoice.id == result["invoice_id"])
            .first()
        )
        assert invoice is not None
        assert invoice.patient_id == test_patient.id
        assert result["amount"] == 12_500.0
        assert result["description"] == "unit invoice"
        assert invoice.provider_data == {"created_by_id": admin_user.id}
        assert result["remaining_amount"] == 12_500
        assert result["available_actions"] == []
        assert result["online_payment_block_reason"] == "invoice_not_linked"

    def test_create_invoice_emits_safe_patient_telegram_unpaid_bill_event(
        self, db_session, admin_user, test_patient, monkeypatch
    ):
        telegram_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(
            payment_invoice_service_module.notification_sender_service,
            "send_patient_telegram_event_notification",
            telegram_mock,
        )

        service = PaymentInvoiceService(db_session)
        result = service.create_invoice(
            amount=18_000.0,
            currency="UZS",
            provider="click",
            description="cardiology invoice",
            patient_id=test_patient.id,
            created_by_id=admin_user.id,
        )

        telegram_mock.assert_awaited_once()
        kwargs = telegram_mock.await_args.kwargs
        assert kwargs["db"] is db_session
        assert kwargs["patient_id"] == test_patient.id
        assert kwargs["event_type"] == "payment_created"
        assert kwargs["metadata"] == {
            "amount": 18_000.0,
            "currency": "UZS",
            "status": "pending",
            "provider": "click",
        }
        assert "invoice_id" not in kwargs["metadata"]
        assert "payment_id" not in kwargs["metadata"]
        assert "provider_payment_id" not in kwargs["metadata"]
        assert result["invoice_id"]

    @pytest.mark.parametrize("patient_id", [0, -1, True, "bad-id"])
    def test_create_invoice_rejects_invalid_patient_id_without_notification(
        self, db_session, admin_user, monkeypatch, patient_id
    ):
        telegram_mock = AsyncMock(return_value=True)
        monkeypatch.setattr(
            payment_invoice_service_module.notification_sender_service,
            "send_patient_telegram_event_notification",
            telegram_mock,
        )

        service = PaymentInvoiceService(db_session)
        with pytest.raises(PaymentInvoiceDomainError) as exc_info:
            service.create_invoice(
                amount=12_500.0,
                currency="UZS",
                provider="click",
                description="unit invoice",
                patient_id=patient_id,  # type: ignore[arg-type]
                created_by_id=admin_user.id,
            )

        assert exc_info.value.status_code == 400
        telegram_mock.assert_not_awaited()

    def test_create_invoice_rejects_unknown_patient(self, db_session):
        service = PaymentInvoiceService(db_session)

        with pytest.raises(PaymentInvoiceDomainError) as exc_info:
            service.create_invoice(
                amount=10_000.0,
                currency="UZS",
                provider="click",
                description=None,
                patient_id=999_999_999,
                created_by_id=None,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail == "Пациент не найден"
        assert db_session.query(PaymentInvoice).count() == 0

    def test_create_invoice_rejects_soft_deleted_patient(
        self, db_session, test_patient
    ):
        test_patient.is_deleted = True
        db_session.commit()
        service = PaymentInvoiceService(db_session)

        with pytest.raises(PaymentInvoiceDomainError) as exc_info:
            service.create_invoice(
                amount=10_000.0,
                currency="UZS",
                provider="click",
                description=None,
                patient_id=test_patient.id,
                created_by_id=None,
            )

        assert exc_info.value.status_code == 404
        assert db_session.query(PaymentInvoice).count() == 0

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

    def test_cart_invoice_without_provider_exposes_backend_owned_click_action(
        self,
        db_session,
        test_visit,
    ):
        invoice = _create_linked_invoice(db_session, test_visit, amount=100_000)

        invoices = PaymentInvoiceService(
            db_session, payment_manager=_PaymentManagerStub()
        ).list_pending_invoices(actor_role="Registrar")
        result = next(row for row in invoices if row["invoice_id"] == invoice.id)

        assert result["provider"] is None
        assert result["payment_method"] == "cash"
        assert result["paid_amount"] == 0
        assert result["remaining_amount"] == 100_000
        assert result["available_actions"] == [
            {"action": "start_online_payment", "provider": "click"}
        ]
        assert result["online_payment_block_reason"] is None

    def test_partial_cart_invoice_exposes_debt_but_blocks_unsafe_online_charge(
        self,
        db_session,
        test_visit,
    ):
        invoice = _create_linked_invoice(db_session, test_visit, amount=100_000)
        db_session.add(
            Payment(
                visit_id=test_visit.id,
                amount=30_000,
                currency="UZS",
                method="cash",
                status="paid",
            )
        )
        db_session.commit()

        invoices = PaymentInvoiceService(
            db_session, payment_manager=_PaymentManagerStub()
        ).list_pending_invoices(actor_role="Registrar")
        result = next(row for row in invoices if row["invoice_id"] == invoice.id)

        assert result["paid_amount"] == 30_000
        assert result["remaining_amount"] == 70_000
        assert result["available_actions"] == []
        assert (
            result["online_payment_block_reason"]
            == "partial_online_payment_not_supported"
        )

    def test_invoice_allocation_mismatch_blocks_online_charge(
        self,
        db_session,
        test_visit,
    ):
        invoice = _create_linked_invoice(db_session, test_visit, amount=100_000)
        invoice.visits[0].visit_amount = 80_000
        db_session.commit()

        invoices = PaymentInvoiceService(
            db_session, payment_manager=_PaymentManagerStub()
        ).list_pending_invoices(actor_role="Registrar")
        result = next(row for row in invoices if row["invoice_id"] == invoice.id)

        assert result["available_actions"] == []
        assert result["online_payment_block_reason"] == "invoice_allocation_mismatch"

    def test_requested_hosted_provider_does_not_switch_when_unavailable(
        self,
        db_session,
        test_visit,
    ):
        invoice = _create_linked_invoice(
            db_session,
            test_visit,
            amount=50_000,
            payment_method="payme",
            provider=None,
        )

        invoices = PaymentInvoiceService(
            db_session, payment_manager=_PaymentManagerStub()
        ).list_pending_invoices(actor_role="Registrar")
        result = next(row for row in invoices if row["invoice_id"] == invoice.id)

        assert result["available_actions"] == []
        assert result["online_payment_block_reason"] == "provider_unavailable"

    def test_new_edit_delta_invoice_is_not_mistaken_for_partial_payment(
        self,
        db_session,
        test_visit,
    ):
        invoice = _create_linked_invoice(
            db_session,
            test_visit,
            amount=20_000,
            service_amount=120_000,
        )
        db_session.add(
            Payment(
                visit_id=test_visit.id,
                amount=100_000,
                currency="UZS",
                method="cash",
                status="paid",
            )
        )
        db_session.commit()

        invoices = PaymentInvoiceService(
            db_session, payment_manager=_PaymentManagerStub()
        ).list_pending_invoices(actor_role="Registrar")
        result = next(row for row in invoices if row["invoice_id"] == invoice.id)

        assert result["paid_amount"] == 0
        assert result["remaining_amount"] == 20_000
        assert result["available_actions"] == [
            {"action": "start_online_payment", "provider": "click"}
        ]
        assert result["online_payment_block_reason"] is None

    def test_cashier_receives_balance_without_registrar_checkout_command(
        self,
        db_session,
        test_visit,
    ):
        invoice = _create_linked_invoice(db_session, test_visit, amount=40_000)

        invoices = PaymentInvoiceService(
            db_session, payment_manager=_PaymentManagerStub()
        ).list_pending_invoices(actor_role="Cashier")
        result = next(row for row in invoices if row["invoice_id"] == invoice.id)

        assert result["remaining_amount"] == 40_000
        assert result["available_actions"] == []
        assert result["online_payment_block_reason"] == "role_not_allowed"

    def test_pending_invoice_action_is_hidden_when_visit_checkout_is_processing(
        self,
        db_session,
        test_visit,
    ):
        pending_invoice = _create_linked_invoice(
            db_session,
            test_visit,
            amount=40_000,
        )
        processing_invoice = PaymentInvoice(
            patient_id=test_visit.patient_id,
            total_amount=40_000,
            currency="UZS",
            status="processing",
            payment_method="click",
            provider="click",
            provider_payment_id="click-in-progress",
        )
        db_session.add(processing_invoice)
        db_session.flush()
        db_session.add(
            PaymentInvoiceVisit(
                invoice_id=processing_invoice.id,
                visit_id=test_visit.id,
                visit_amount=40_000,
            )
        )
        db_session.commit()

        invoices = PaymentInvoiceService(
            db_session, payment_manager=_PaymentManagerStub()
        ).list_pending_invoices(actor_role="Registrar")
        result = next(
            row for row in invoices if row["invoice_id"] == pending_invoice.id
        )

        assert result["available_actions"] == []
        assert result["online_payment_block_reason"] == "invoice_payment_in_progress"

from __future__ import annotations

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.api.v1.endpoints.registrar_wizard import _invoice as invoice_module
from app.api.v1.endpoints.registrar_wizard._helpers import InvoicePaymentRequest
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import VisitService
from app.services.payment_invariant_service import PaymentInvariantService


def _create_invoice(
    db_session,
    test_visit,
    *,
    amount: int = 125_000,
    service_amount: int | None = None,
    linked: bool = True,
    provider: str | None = None,
    payment_method: str = "cash",
) -> PaymentInvoice:
    if linked:
        db_session.add(
            VisitService(
                visit_id=test_visit.id,
                service_id=1,
                name="SYNTHETIC-registrar invoice checkout",
                qty=1,
                price=service_amount if service_amount is not None else amount,
            )
        )
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=amount,
        currency="UZS",
        provider=provider,
        status="pending",
        payment_method=payment_method,
    )
    db_session.add(invoice)
    db_session.flush()
    if linked:
        db_session.add(
            PaymentInvoiceVisit(
                invoice_id=invoice.id,
                visit_id=test_visit.id,
                visit_amount=amount,
            )
        )
    db_session.commit()
    return invoice


def _manager(*, supported: set[str]) -> Mock:
    manager = Mock()
    manager.get_provider_info.return_value = {
        provider: {"supported_currencies": ["UZS"]}
        for provider in supported
    }
    manager.supports_registrar_invoice_payment.side_effect = (
        lambda provider: provider.lower() in supported
    )
    return manager


def _registrar() -> SimpleNamespace:
    return SimpleNamespace(id=7, role="Registrar")


@pytest.mark.unit
def test_invoice_payment_rejects_invoice_without_payable_visit_link(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(db_session, test_visit, linked=False)
    manager_factory = Mock()
    monkeypatch.setattr(invoice_module, "get_payment_manager", manager_factory)

    with pytest.raises(invoice_module.HTTPException) as exc_info:
        invoice_module.init_invoice_payment(
            payment_req=InvoicePaymentRequest(
                invoice_id=invoice.id,
                provider="click",
            ),
            db=db_session,
            current_user=_registrar(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail == "Счёт не связан с оплачиваемыми визитами"
    assert invoice.status == "pending"
    manager_factory.assert_not_called()


@pytest.mark.unit
def test_invoice_payment_rejects_payme_before_emitting_unreconciled_link(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(
        db_session,
        test_visit,
        provider="payme",
        payment_method="payme",
    )
    manager = _manager(supported={"click"})
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    response = invoice_module.init_invoice_payment(
        payment_req=InvoicePaymentRequest(invoice_id=invoice.id, provider="payme"),
        db=db_session,
        current_user=_registrar(),
    )

    assert response.success is False
    assert "не поддерживается" in (response.error_message or "")
    assert invoice.status == "pending"
    manager.supports_registrar_invoice_payment.assert_called_once_with("payme")
    manager.create_payment.assert_not_called()


@pytest.mark.unit
def test_invoice_payment_uses_backend_authorized_click_action(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(db_session, test_visit)
    manager = _manager(supported={"click"})
    manager.create_payment.return_value = SimpleNamespace(
        success=True,
        payment_id="click-payment-42",
        payment_url="https://my.click.uz/pay/42",
        provider_data={"merchant_trans_id": f"invoice_{invoice.id}"},
    )
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    response = invoice_module.init_invoice_payment(
        payment_req=InvoicePaymentRequest(invoice_id=invoice.id, provider="CLICK"),
        db=db_session,
        current_user=_registrar(),
    )

    assert response.success is True
    assert response.payment_url == "https://my.click.uz/pay/42"
    manager.create_payment.assert_called_once_with(
        provider_name="click",
        amount=Decimal("125000"),
        currency="UZS",
        order_id=f"invoice_{invoice.id}",
        description=f"Оплата визитов #{invoice.id}",
        return_url=None,
        cancel_url=None,
    )
    db_session.refresh(invoice)
    assert invoice.provider_payment_id == "click-payment-42"
    assert invoice.payment_method == "click"
    assert invoice.provider == "click"
    assert invoice.status == "processing"


@pytest.mark.unit
def test_invoice_payment_revalidates_residual_debt_before_provider_call(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(db_session, test_visit)
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
    manager = _manager(supported={"click"})
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    with pytest.raises(invoice_module.HTTPException) as exc_info:
        invoice_module.init_invoice_payment(
            payment_req=InvoicePaymentRequest(
                invoice_id=invoice.id,
                provider="click",
            ),
            db=db_session,
            current_user=_registrar(),
        )

    assert exc_info.value.status_code == 409
    assert "Обновите список счетов" in str(exc_info.value.detail)
    manager.create_payment.assert_not_called()
    db_session.refresh(invoice)
    assert invoice.status == "pending"


@pytest.mark.unit
def test_invoice_payment_rejects_allocation_mismatch_before_provider_call(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(db_session, test_visit)
    invoice.visits[0].visit_amount = 100_000
    db_session.commit()
    manager = _manager(supported={"click"})
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    with pytest.raises(invoice_module.HTTPException) as exc_info:
        invoice_module.init_invoice_payment(
            payment_req=InvoicePaymentRequest(
                invoice_id=invoice.id,
                provider="click",
            ),
            db=db_session,
            current_user=_registrar(),
        )

    assert exc_info.value.status_code == 409
    assert "Распределение суммы счёта" in str(exc_info.value.detail)
    manager.create_payment.assert_not_called()
    db_session.refresh(invoice)
    assert invoice.status == "pending"


@pytest.mark.unit
def test_invoice_payment_cannot_bypass_backend_provider_binding(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(
        db_session,
        test_visit,
        provider=None,
        payment_method="payme",
    )
    manager = _manager(supported={"click", "payme"})
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    with pytest.raises(invoice_module.HTTPException) as exc_info:
        invoice_module.init_invoice_payment(
            payment_req=InvoicePaymentRequest(
                invoice_id=invoice.id,
                provider="click",
            ),
            db=db_session,
            current_user=_registrar(),
        )

    assert exc_info.value.status_code == 409
    manager.create_payment.assert_not_called()


@pytest.mark.unit
def test_processing_invoice_reserves_visit_from_counter_payment(
    db_session,
    test_visit,
):
    invoice = _create_invoice(db_session, test_visit)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.provider_payment_id = "click-reservation"
    db_session.commit()

    with pytest.raises(invoice_module.HTTPException) as exc_info:
        PaymentInvariantService(db_session).create_payment_for_visit(
            visit_id=test_visit.id,
            amount=Decimal("1000"),
            method="cash",
            note=None,
            current_user=_registrar(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["reason"] == "invoice_payment_in_progress"
    assert db_session.query(Payment).count() == 0


@pytest.mark.unit
def test_pending_invoice_cannot_start_while_same_visit_checkout_is_processing(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    pending_invoice = _create_invoice(db_session, test_visit)
    processing_invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=125_000,
        currency="UZS",
        provider="click",
        status="processing",
        payment_method="click",
        provider_payment_id="click-existing-checkout",
    )
    db_session.add(processing_invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=processing_invoice.id,
            visit_id=test_visit.id,
            visit_amount=125_000,
        )
    )
    db_session.commit()
    manager = _manager(supported={"click"})
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    with pytest.raises(invoice_module.HTTPException) as exc_info:
        invoice_module.init_invoice_payment(
            payment_req=InvoicePaymentRequest(
                invoice_id=pending_invoice.id,
                provider="click",
            ),
            db=db_session,
            current_user=_registrar(),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["reason"] == "invoice_payment_in_progress"
    manager.create_payment.assert_not_called()


@pytest.mark.unit
def test_completed_invoice_records_delta_even_with_historical_payment(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(
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
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.payment_method = "click"
    invoice.provider_payment_id = "click-delta-settlement"
    db_session.commit()
    manager = _manager(supported={"click"})
    manager.check_payment_status.return_value = SimpleNamespace(
        success=True,
        status="completed",
    )
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    response = invoice_module.check_invoice_status(
        invoice_id=invoice.id,
        db=db_session,
        current_user=_registrar(),
    )

    assert response["status"] == "paid"
    provider_receipts = (
        db_session.query(Payment)
        .filter(Payment.provider_payment_id == "click-delta-settlement")
        .all()
    )
    assert len(provider_receipts) == 1
    assert provider_receipts[0].amount == Decimal("20000")
    assert provider_receipts[0].provider == "click"

    second_response = invoice_module.check_invoice_status(
        invoice_id=invoice.id,
        db=db_session,
        current_user=_registrar(),
    )
    assert second_response["status"] == "paid"
    assert (
        db_session.query(Payment)
        .filter(Payment.provider_payment_id == "click-delta-settlement")
        .count()
        == 1
    )


@pytest.mark.unit
def test_completed_invoice_rejects_allocation_mismatch_before_recording_receipts(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(db_session, test_visit)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.payment_method = "click"
    invoice.provider_payment_id = "click-mismatched-allocation"
    invoice.visits[0].visit_amount = 100_000
    db_session.commit()
    manager = _manager(supported={"click"})
    manager.check_payment_status.return_value = SimpleNamespace(
        success=True,
        status="completed",
    )
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    with pytest.raises(invoice_module.HTTPException) as exc_info:
        invoice_module.check_invoice_status(
            invoice_id=invoice.id,
            db=db_session,
            current_user=_registrar(),
        )

    assert exc_info.value.status_code == 409
    assert "Распределение суммы счёта" in str(exc_info.value.detail)
    assert db_session.query(Payment).count() == 0
    db_session.refresh(invoice)
    assert invoice.status == "processing"


@pytest.mark.unit
def test_completed_invoice_aggregates_duplicate_visit_allocations(
    db_session,
    test_visit,
    monkeypatch: pytest.MonkeyPatch,
):
    invoice = _create_invoice(db_session, test_visit)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.payment_method = "click"
    invoice.provider_payment_id = "click-duplicate-allocation"
    invoice.visits[0].visit_amount = 75_000
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id,
            visit_id=test_visit.id,
            visit_amount=50_000,
        )
    )
    db_session.commit()
    manager = _manager(supported={"click"})
    manager.check_payment_status.return_value = SimpleNamespace(
        success=True,
        status="completed",
    )
    monkeypatch.setattr(
        invoice_module,
        "get_payment_manager",
        Mock(return_value=manager),
    )

    response = invoice_module.check_invoice_status(
        invoice_id=invoice.id,
        db=db_session,
        current_user=_registrar(),
    )

    assert response["status"] == "paid"
    receipts = (
        db_session.query(Payment)
        .filter(Payment.provider_payment_id == "click-duplicate-allocation")
        .all()
    )
    assert len(receipts) == 1
    assert receipts[0].amount == Decimal("125000")

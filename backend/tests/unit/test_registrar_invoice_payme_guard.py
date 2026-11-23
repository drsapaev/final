from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.api.v1.endpoints.registrar_wizard import _invoice as invoice_module
from app.api.v1.endpoints.registrar_wizard._helpers import InvoicePaymentRequest
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.visit import Visit, VisitService
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
                currency="UZS",
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


def _observed_checkout(invoice: PaymentInvoice, *, outcome: str = "completed", **overrides) -> SimpleNamespace:
    provider_data = {
        "merchant_trans_id": invoice.provider_payment_id,
        "status": {"completed": 2, "failed": -1, "cancelled": -2}[outcome],
        "amount": str(invoice.total_amount),
        "currency": "UZS",
        "click_trans_id": "10203",
    }
    provider_data.update(overrides)
    return SimpleNamespace(
        success=True, status=outcome, payment_id=invoice.provider_payment_id, provider_data=provider_data,
    )


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


def test_zero_amount_processing_link_still_reserves_visit(db_session, test_visit):
    invoice = _create_invoice(db_session, test_visit)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.provider_payment_id = "synthetic-checkout"
    invoice.visits[0].visit_amount = Decimal("0.00")
    db_session.commit()
    with pytest.raises(invoice_module.HTTPException) as exc_info:
        PaymentInvariantService(db_session).assert_no_processing_invoice_reservation([test_visit.id])
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["reason"] == "invoice_payment_in_progress"


def test_checkout_context_locks_zero_link_and_detects_per_visit_staleness(db_session, test_visit):
    invoice = _create_invoice(db_session, test_visit, amount=100)
    second = Visit(patient_id=test_visit.patient_id, status="open", confirmation_context_epoch=1)
    db_session.add(second)
    db_session.flush()
    line = VisitService(
        visit_id=second.id, service_id=2, name="SYNTHETIC",
        qty=1, price=Decimal("0.00"), currency="UZS",
    )
    link = PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=second.id, visit_amount=Decimal("0.00"))
    db_session.add_all([line, link])
    db_session.commit()
    _, visits, links = invoice_module._lock_invoice_settlement_context(db_session, invoice.id)
    assert {visit.id for visit in visits} == {test_visit.id, second.id}
    assert {item.visit_id for item in links} == {test_visit.id, second.id}
    # Aggregate remains 100 while each allocation is now wrong.
    line.price = Decimal("10.00")
    next(item for item in invoice.visits if item.visit_id == test_visit.id).visit_amount = Decimal("90.00")
    link.visit_amount = Decimal("10.00")
    db_session.flush()
    with pytest.raises(invoice_module.HTTPException) as error:
        invoice_module._lock_invoice_settlement_context(db_session, invoice.id)
    assert error.value.status_code == 409


def test_checkout_checks_pending_all_free_in_zero_allocation(db_session, test_visit, monkeypatch):
    invoice = _create_invoice(db_session, test_visit)
    pending = Visit(
        patient_id=test_visit.patient_id, status="pending_confirmation",
        discount_mode="all_free", approval_status="pending", confirmation_context_epoch=1,
    )
    db_session.add(pending)
    db_session.flush()
    db_session.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=pending.id, visit_amount=Decimal("0")))
    db_session.commit()
    manager_factory = Mock()
    monkeypatch.setattr(invoice_module, "get_payment_manager", manager_factory)

    with pytest.raises(invoice_module.HTTPException) as error:
        invoice_module.init_invoice_payment(
            InvoicePaymentRequest(invoice_id=invoice.id, provider="click"), db_session, _registrar(),
        )
    assert error.value.status_code == 409
    assert error.value.detail == "Визит All Free ожидает решения администратора"
    manager_factory.assert_not_called()


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
    manager.check_payment_status.return_value = _observed_checkout(invoice)
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
    assert provider_receipts[0].provider_transaction_id == "10203"

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
    manager.check_payment_status.return_value = _observed_checkout(invoice)
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
    manager.check_payment_status.return_value = _observed_checkout(invoice)
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


@pytest.mark.parametrize(
    "overrides",
    [
        {"merchant_trans_id": None},
        {"amount": "124999.99"},
        {"currency": "USD"},
        {"status": 0},
        {"click_trans_id": None},
    ],
)
def test_completed_status_without_exact_receipt_evidence_leaves_invoice_unsettled(
    db_session, test_visit, monkeypatch, overrides,
):
    invoice = _create_invoice(db_session, test_visit)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.provider_payment_id = "synthetic-status-binding"
    db_session.commit()
    manager = _manager(supported={"click"})
    manager.check_payment_status.return_value = _observed_checkout(invoice, **overrides)
    monkeypatch.setattr(invoice_module, "get_payment_manager", lambda: manager)

    with pytest.raises(invoice_module.HTTPException) as rejected:
        invoice_module.check_invoice_status(invoice.id, db_session, _registrar())

    assert rejected.value.status_code == 409
    assert db_session.query(Payment).count() == 0
    assert invoice.status == "processing"


def test_stale_provider_cancellation_cannot_change_the_current_checkout(
    db_session, test_visit, monkeypatch,
):
    invoice = _create_invoice(db_session, test_visit)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.provider_payment_id = "synthetic-before-refresh"
    db_session.commit()
    old_observation = _observed_checkout(invoice, outcome="cancelled")
    manager = _manager(supported={"click"})

    def status_after_checkout_changed(*_):
        invoice.provider_payment_id = "synthetic-new-checkout"
        db_session.commit()
        return old_observation

    manager.check_payment_status.side_effect = status_after_checkout_changed
    monkeypatch.setattr(invoice_module, "get_payment_manager", lambda: manager)

    with pytest.raises(invoice_module.HTTPException) as rejected:
        invoice_module.check_invoice_status(invoice.id, db_session, _registrar())

    assert rejected.value.status_code == 409
    assert invoice.status == "processing"
    assert invoice.provider_payment_id == "synthetic-new-checkout"


def test_captured_group_records_positive_visits_only(db_session, test_visit, monkeypatch):
    invoice = _create_invoice(db_session, test_visit, amount=60_000)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.provider_payment_id = "synthetic-group-settlement"
    invoice.total_amount = Decimal("100000.00")
    second = Visit(
        patient_id=test_visit.patient_id, doctor_id=test_visit.doctor_id,
        visit_date=test_visit.visit_date, status="pending_confirmation", confirmation_context_epoch=1,
    )
    zero = Visit(
        patient_id=test_visit.patient_id, status="pending_confirmation", confirmation_context_epoch=1,
        discount_mode="all_free", approval_status="pending",
    )
    db_session.add_all([second, zero])
    db_session.flush()
    db_session.add_all([
        VisitService(
            visit_id=second.id, service_id=1, name="SYNTHETIC second visit",
            qty=1, price=Decimal("40000.00"), currency="UZS",
        ),
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=second.id, visit_amount=Decimal("40000.00")),
        PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=zero.id, visit_amount=Decimal("0.00")),
    ])
    db_session.commit()
    manager = _manager(supported={"click"})
    manager.check_payment_status.return_value = _observed_checkout(invoice)
    monkeypatch.setattr(invoice_module, "get_payment_manager", lambda: manager)

    assert invoice_module.check_invoice_status(invoice.id, db_session, _registrar())["status"] == "paid"
    assert invoice.provider_transaction_id == "10203"
    amounts = {
        receipt.visit_id: receipt.amount
        for receipt in db_session.query(Payment).filter_by(provider_payment_id=invoice.provider_payment_id)
    }
    assert amounts == {test_visit.id: Decimal("60000.00"), second.id: Decimal("40000.00")}
    assert zero.status == "pending_confirmation"


def test_provider_completion_does_not_apply_redistributed_allocation(db_session, test_visit, monkeypatch):
    invoice = _create_invoice(db_session, test_visit)
    invoice.status = "processing"
    invoice.provider = "click"
    invoice.provider_payment_id = "synthetic-redistributed-allocation"
    second = Visit(patient_id=test_visit.patient_id, status="open", confirmation_context_epoch=1)
    db_session.add(second)
    db_session.flush()
    link = PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=second.id, visit_amount=Decimal("0.00"))
    db_session.add(link)
    db_session.commit()
    observed = _observed_checkout(invoice)
    manager = _manager(supported={"click"})

    def change_allocation_during_check(*_):
        primary = next(item for item in invoice.visits if item.visit_id == test_visit.id)
        primary.visit_amount -= Decimal("1.00")
        link.visit_amount += Decimal("1.00")
        db_session.commit()
        return observed

    manager.check_payment_status.side_effect = change_allocation_during_check
    monkeypatch.setattr(invoice_module, "get_payment_manager", lambda: manager)

    with pytest.raises(invoice_module.HTTPException) as rejected:
        invoice_module.check_invoice_status(invoice.id, db_session, _registrar())

    assert rejected.value.status_code == 409
    assert invoice.status == "processing"
    assert db_session.query(Payment).count() == 0


def test_invoice_status_returns_only_already_issued_tickets_for_its_patient(
    client, db_session, auth_headers, test_visit, patient_token, monkeypatch,
):
    invoice = _create_invoice(db_session, test_visit)
    test_visit.status = "confirmed"
    other_patient = Patient(first_name="Synthetic", last_name="Other")
    db_session.add(other_patient)
    db_session.flush()
    unrelated_visit = Visit(
        patient_id=test_visit.patient_id,
        visit_date=test_visit.visit_date,
        status="confirmed",
    )
    foreign_visit = Visit(
        patient_id=other_patient.id,
        visit_date=test_visit.visit_date,
        status="confirmed",
    )
    benefit_visit = Visit(
        patient_id=test_visit.patient_id,
        visit_date=test_visit.visit_date,
        status="confirmed",
        discount_mode="all_free",
        approval_status="pending",
    )
    db_session.add_all([unrelated_visit, foreign_visit, benefit_visit])
    ready = DailyQueue(
        day=test_visit.visit_date, queue_tag="cardiology_common",
        specialist_id=test_visit.doctor_id, active=True, cabinet_number="37",
    )
    archive = DailyQueue(
        day=test_visit.visit_date, queue_tag="cardiology_archive",
        specialist_id=test_visit.doctor_id, active=False,
    )
    old_date = DailyQueue(
        day=test_visit.visit_date - timedelta(days=1), queue_tag="cardiology_common",
        specialist_id=test_visit.doctor_id, active=True,
    )
    db_session.add_all([ready, archive, old_date])
    db_session.flush()
    db_session.add_all(
        [
            PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit_id, visit_amount=0)
            for visit_id in (test_visit.id, foreign_visit.id, benefit_visit.id)
        ]
    )
    issued = [
        (ready, test_visit, test_visit.patient_id, 41, "waiting"),
        (archive, test_visit, test_visit.patient_id, 42, "completed"),
        (archive, test_visit, test_visit.patient_id, 43, "waiting"),
        (ready, test_visit, test_visit.patient_id, 44, "cancelled"),
        (ready, test_visit, other_patient.id, 45, "waiting"),
        (ready, foreign_visit, other_patient.id, 46, "waiting"),
        (ready, unrelated_visit, test_visit.patient_id, 47, "waiting"),
        (old_date, test_visit, test_visit.patient_id, 48, "waiting"),
        (ready, benefit_visit, test_visit.patient_id, 49, "waiting"),
    ]
    db_session.add_all(
        [
            OnlineQueueEntry(
                queue_id=queue.id, visit_id=visit.id, patient_id=patient_id,
                number=number, status=status,
            )
            for queue, visit, patient_id, number, status in issued
        ]
    )
    db_session.commit()
    payment_manager = Mock(side_effect=AssertionError("paid and pending reads use stored state"))
    monkeypatch.setattr(invoice_module, "get_payment_manager", payment_manager)
    endpoint = f"/api/v1/registrar/invoice/{invoice.id}/status"

    pending = client.get(endpoint, headers=auth_headers)
    assert pending.status_code == 200
    assert pending.headers["cache-control"] == "private, no-store"
    assert pending.json()["print_tickets"] == []

    invoice.status = "paid"
    db_session.commit()
    receipt_count = db_session.query(Payment).count()
    queue_count = db_session.query(OnlineQueueEntry).count()
    first = client.get(endpoint, headers=auth_headers)
    second = client.get(endpoint, headers=auth_headers)

    assert first.status_code == second.status_code == 200
    assert first.headers["cache-control"] == second.headers["cache-control"] == "private, no-store"
    assert first.json() == second.json()
    assert first.json()["status"] == "paid"
    denied = client.get(endpoint, headers={"Authorization": f"Bearer {patient_token}"})
    assert denied.status_code == 403
    assert "print_tickets" not in denied.json()
    tickets = first.json()["print_tickets"]
    assert [(t["queue_id"], t["queue_number"]) for t in tickets] == [
        (ready.id, 41),
        (archive.id, 42),
    ]
    assert all(t["visit_id"] == test_visit.id and t["patient_id"] == test_visit.patient_id for t in tickets)
    assert tickets[0]["doctor_cabinet"] == "37"
    assert set(tickets[0]) == {
        "visit_id", "queue_tag", "queue_name", "queue_number", "queue_id",
        "patient_id", "patient_name", "doctor_name", "doctor_cabinet",
        "department", "visit_date", "visit_time",
    }
    assert db_session.query(Payment).count() == receipt_count
    assert db_session.query(OnlineQueueEntry).count() == queue_count
    payment_manager.assert_not_called()

"""Payment interlocks for visits awaiting an All Free decision."""

from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.v1.endpoints.force_majeure import UseDepositRequest
from app.api.v1.endpoints.registrar_wizard import _invoice
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.refund_deposit import DepositTransaction, PatientDeposit
from app.models.visit import Visit, VisitService
from app.services.all_free_approval import ALL_FREE_DECISION_REQUIRED
from app.services.force_majeure_api_service import (
    ForceMajeureApiDomainError,
    ForceMajeureApiService,
)
from app.services.payment_init_service import PaymentInitService
from app.services.payment_invariant_service import PaymentInvariantService
from tests.integration.test_all_free_decision_concurrency_pg import (  # noqa: F401
    approval_case,
)

pytestmark = pytest.mark.integration

AMOUNT = Decimal("50000.00")


def _add_charge(db, visit, service):
    db.add(
        VisitService(
            visit_id=visit.id,
            service_id=service.id,
            name="Synthetic consultation",
            qty=1,
            price=AMOUNT,
        )
    )


@pytest.mark.parametrize("approval_status", ["pending", "none"])
def test_cash_and_group_receipts_wait_for_decision(
    db_session, test_visit, test_service, admin_user, approval_status
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = approval_status
    _add_charge(db_session, test_visit, test_service)
    db_session.commit()
    payment = PaymentInvariantService(db_session)

    with pytest.raises(HTTPException) as direct_error:
        payment.create_payment_for_visit(
            test_visit.id, AMOUNT, "cash", None, admin_user
        )
    with pytest.raises(HTTPException) as group_error:
        payment.receive_grouped_payment(
            visit_ids=[test_visit.id],
            amount=AMOUNT,
            method="cash",
            current_user=admin_user,
        )

    for error in (direct_error, group_error):
        assert error.value.status_code == 409
        assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    assert db_session.query(Payment).filter_by(visit_id=test_visit.id).count() == 0


def test_provider_initialization_waits_without_creating_a_payment(
    db_session, test_visit, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    db_session.commit()
    manager = Mock()
    manager.get_providers_for_currency.return_value = ["click"]

    result = PaymentInitService(db_session, manager).init_payment(
        request=SimpleNamespace(state=None),
        current_user_id=admin_user.id,
        visit_id=test_visit.id,
        provider="click",
        amount=float(AMOUNT),
        currency="UZS",
        description=None,
        return_url=None,
        cancel_url=None,
    )

    assert result["success"] is False
    assert ALL_FREE_DECISION_REQUIRED in result["error_message"]
    manager.create_payment.assert_not_called()
    assert db_session.query(Payment).filter_by(visit_id=test_visit.id).count() == 0


def test_invoice_initialization_checks_pending_zero_price_member(
    db_session, test_visit, test_service, admin_user, monkeypatch
):
    pending_visit = Visit(
        patient_id=test_visit.patient_id,
        visit_date=test_visit.visit_date,
        status="pending_confirmation",
        discount_mode="all_free",
        approval_status="pending",
    )
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=AMOUNT,
        status="pending",
        currency="UZS",
    )
    db_session.add_all([pending_visit, invoice])
    _add_charge(db_session, test_visit, test_service)
    db_session.flush()
    db_session.add_all(
        [
            PaymentInvoiceVisit(
                invoice_id=invoice.id, visit_id=test_visit.id, visit_amount=AMOUNT
            ),
            PaymentInvoiceVisit(
                invoice_id=invoice.id, visit_id=pending_visit.id, visit_amount=0
            ),
        ]
    )
    db_session.commit()
    factory = Mock()
    monkeypatch.setattr(_invoice, "get_payment_manager", factory)

    with pytest.raises(HTTPException) as error:
        _invoice.init_invoice_payment(
            _invoice.InvoicePaymentRequest(invoice_id=invoice.id, provider="click"),
            db_session,
            admin_user,
        )

    assert error.value.status_code == 409
    assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    assert db_session.get(PaymentInvoice, invoice.id).status == "pending"
    factory.assert_not_called()


def test_deposit_debit_preserves_balance_until_decision(
    db_session, test_visit, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    deposit = PatientDeposit(
        patient_id=test_visit.patient_id, currency="UZS", balance=AMOUNT, is_active=True
    )
    db_session.add(deposit)
    db_session.commit()

    with pytest.raises(ForceMajeureApiDomainError) as error:
        ForceMajeureApiService(db_session).use_deposit_for_payment(
            request=UseDepositRequest(
                patient_id=test_visit.patient_id, visit_id=test_visit.id, amount=AMOUNT
            ),
            current_user_id=admin_user.id,
        )

    assert error.value.status_code == 409
    assert error.value.detail == ALL_FREE_DECISION_REQUIRED
    assert db_session.get(PatientDeposit, deposit.id).balance == AMOUNT
    assert (
        db_session.query(DepositTransaction).filter_by(deposit_id=deposit.id).count()
        == 0
    )


def test_rejected_visit_can_pay_persisted_regular_price(
    db_session, test_visit, test_service, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "rejected"
    _add_charge(db_session, test_visit, test_service)
    db_session.commit()

    payment = PaymentInvariantService(db_session).create_payment_for_visit(
        test_visit.id, AMOUNT, "cash", None, admin_user, allow_overpayment=False
    )

    assert payment.amount == AMOUNT
    assert payment.status == "paid"


def test_prior_invoice_settlement_can_record_already_received_funds(
    db_session, test_visit, test_service, admin_user
):
    test_visit.discount_mode = "all_free"
    test_visit.approval_status = "pending"
    _add_charge(db_session, test_visit, test_service)
    invoice = PaymentInvoice(
        patient_id=test_visit.patient_id,
        total_amount=AMOUNT,
        status="processing",
        currency="UZS",
        provider="click",
    )
    db_session.add(invoice)
    db_session.flush()
    db_session.add(
        PaymentInvoiceVisit(
            invoice_id=invoice.id, visit_id=test_visit.id, visit_amount=AMOUNT
        )
    )
    db_session.commit()

    payment = PaymentInvariantService(db_session).create_payment_for_visit(
        test_visit.id,
        AMOUNT,
        "click",
        None,
        admin_user,
        provider="click",
        allow_overpayment=False,
        settling_invoice_id=invoice.id,
    )

    assert payment.amount == AMOUNT
    assert payment.status == "paid"


def test_payment_rereads_committed_approval_under_postgres_lock(approval_case):
    engine, visit_id, _ = approval_case
    with Session(engine) as db:
        db.get(Visit, visit_id).approval_status = "approved"
        db.commit()

    with Session(engine) as payment_db:
        cached_visit = payment_db.get(Visit, visit_id)
        assert cached_visit.approval_status == "approved"
        with Session(engine) as request_db:
            request_db.get(Visit, visit_id).approval_status = "pending"
            request_db.commit()

        with pytest.raises(HTTPException) as error:
            PaymentInvariantService(payment_db).check_payment_allowed(visit_id, AMOUNT)

        assert error.value.status_code == 409
        assert error.value.detail == ALL_FREE_DECISION_REQUIRED
        assert cached_visit.approval_status == "pending"

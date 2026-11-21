"""Intermediate fail-closed financial guards for price approval.

This suite exercises the guard directly; it does not certify the unfinished
invoice re-quote, issuer provenance, notification reissue or concurrent
invoice-writer protocol. All records are synthetic and no provider is called.
"""
from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.models.billing import Invoice, InvoiceStatus
from app.models.doctor_price_override import DoctorPriceOverride
from app.models.payment import Payment, PaymentVisit
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.services.price_override_approval import (
    PriceOverrideApprovalError,
    PriceOverrideApprovalService,
)
from app.services.profile_contact_security import ProfileBearerContext
from tests.integration.test_regprice_approval_integrity import (
    _create_doctor,
    _create_patient,
    _create_service,
    _create_user,
    _create_visit_with_service,
)


@pytest.fixture
def financial_visit(db_session):
    user = _create_user(db_session, role="derma", label="guard")
    doctor = _create_doctor(db_session, user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label="guard", price=Decimal("100.00"))
    visit, row = _create_visit_with_service(
        db_session, patient=patient, doctor=doctor, service=service, price=Decimal("100.00")
    )
    return patient, doctor, service, visit, row


def _payment(db, visit_id, status, *, amount="100.00", refunded=None, paid_at=None):
    payment = Payment(
        visit_id=visit_id,
        amount=Decimal(amount),
        currency="UZS",
        method="online",
        status=status,
        refunded_amount=None if refunded is None else Decimal(refunded),
        paid_at=paid_at,
    )
    db.add(payment)
    db.commit()
    return payment


def _assert_blocked(db, visit_id):
    with pytest.raises(PriceOverrideApprovalError) as exc:
        PriceOverrideApprovalService(db)._assert_no_financial_exposure(visit_id)
    assert exc.value.status_code == 409


def test_unpaid_visit_is_eligible_for_further_approval_checks(db_session, financial_visit):
    _, _, _, visit, _ = financial_visit
    PriceOverrideApprovalService(db_session)._assert_no_financial_exposure(visit.id)


def test_legacy_request_can_be_rejected_even_if_payment_is_pending(
    db_session, financial_visit, admin_user
):
    _, doctor, service, visit, line = financial_visit
    _payment(db_session, visit.id, "pending")
    request = DoctorPriceOverride(
        visit_id=visit.id, doctor_id=doctor.id, service_id=service.id,
        original_price=Decimal("100.00"), new_price=Decimal("90.00"),
        visit_price_before=None, reason="Synthetic request", status="pending",
    )
    db_session.add(request)
    db_session.commit()
    decided = PriceOverrideApprovalService(db_session).process(
        override_id=request.id, action="reject", rejection_reason="Not approved", approver_id=admin_user.id,
        bearer=ProfileBearerContext(admin_user.id, admin_user.auth_epoch, None, None, None),
    )
    db_session.refresh(line)
    assert decided.status == "rejected"
    assert decided.rejection_reason == "Not approved"
    assert line.price == Decimal("100.00")


@pytest.mark.parametrize("status", ["pending", "processing", "failed", "unknown"])
def test_nonterminal_or_unrecognized_payment_blocks_price_change(db_session, financial_visit, status):
    _, _, _, visit, _ = financial_visit
    _payment(db_session, visit.id, status)
    _assert_blocked(db_session, visit.id)


@pytest.mark.parametrize(
    "status,refunded,paid_at",
    [
        ("paid", None, None),
        ("completed", "30.00", None),
        ("refunded", None, datetime(2026, 1, 1, tzinfo=UTC)),
        ("cancelled", None, datetime(2026, 1, 1, tzinfo=UTC)),
        ("void", "30.00", datetime(2026, 1, 1, tzinfo=UTC)),
        ("cancelled", None, None),
        ("void", None, None),
        ("paid", "101.00", datetime(2026, 1, 1, tzinfo=UTC)),
        ("paid", "-1.00", datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_unreconciled_payment_or_partial_refund_blocks_price_change(
    db_session, financial_visit, status, refunded, paid_at
):
    _, _, _, visit, _ = financial_visit
    _payment(db_session, visit.id, status, refunded=refunded, paid_at=paid_at)
    _assert_blocked(db_session, visit.id)


@pytest.mark.parametrize(
    "status,refunded,paid_at",
    [
        ("paid", "100.00", datetime(2026, 1, 1, tzinfo=UTC)),
        ("completed", "100.00", None),
        ("refunded", "100.00", datetime(2026, 1, 1, tzinfo=UTC)),
    ],
)
def test_proven_full_refund_does_not_block_diagnostic(
    db_session, financial_visit, status, refunded, paid_at
):
    _, _, _, visit, _ = financial_visit
    _payment(db_session, visit.id, status, refunded=refunded, paid_at=paid_at)
    PriceOverrideApprovalService(db_session)._assert_no_financial_exposure(visit.id)


def test_legacy_group_payment_link_is_also_checked(db_session, financial_visit):
    patient, doctor, service, visit, _ = financial_visit
    other, _ = _create_visit_with_service(
        db_session, patient=patient, doctor=doctor, service=service, price=Decimal("100.00")
    )
    payment = _payment(db_session, other.id, "paid")
    db_session.add(PaymentVisit(payment_id=payment.id, visit_id=visit.id, amount=Decimal("50.00")))
    db_session.commit()
    _assert_blocked(db_session, visit.id)


@pytest.mark.parametrize("status", ["pending", "processing", "paid", "cancelled"])
def test_group_invoice_link_blocks_until_group_requote_is_implemented(db_session, financial_visit, status):
    patient, _, _, visit, _ = financial_visit
    invoice = PaymentInvoice(patient_id=patient.id, total_amount=Decimal("100.00"), currency="UZS", status=status)
    db_session.add(invoice)
    db_session.flush()
    db_session.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("100.00")))
    db_session.commit()
    _assert_blocked(db_session, visit.id)


def test_zero_amount_invoice_link_is_still_financial_exposure(db_session, financial_visit):
    patient, _, _, visit, _ = financial_visit
    invoice = PaymentInvoice(patient_id=patient.id, total_amount=Decimal("0.00"), currency="UZS", status="pending")
    db_session.add(invoice)
    db_session.flush()
    db_session.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("0.00")))
    db_session.commit()
    _assert_blocked(db_session, visit.id)


@pytest.mark.parametrize("status", [InvoiceStatus.DRAFT, InvoiceStatus.PENDING, InvoiceStatus.CANCELLED])
def test_manual_invoice_blocks_until_its_writers_use_shared_protocol(db_session, financial_visit, status):
    patient, _, _, visit, _ = financial_visit
    db_session.add(Invoice(invoice_number=f"SYNTHETIC-{visit.id}-{status.value}", patient_id=patient.id,
                           visit_id=visit.id, status=status, subtotal=100, total_amount=100, balance=100))
    db_session.commit()
    _assert_blocked(db_session, visit.id)

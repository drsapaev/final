"""CSH-FE-036 (#3813 follow-up): /cashier/stats must expose BOTH financial
semantics — gross receipts AND receipts net of refunds — without silently
changing the meaning of the existing total_amount/cash_amount/card_amount.

Owner decision (2026-11-02): keep both values. The existing fields stay
gross (original amounts of paid/completed payments; a full refund flips the
status to 'refunded' and leaves the gross set entirely). New fields
(``refunded_amount`` + ``net_*``) carry the same period net of refunds.
``pending_amount`` has been net of refunds since CSH-FE-028 (#3814).

This file pins that contract with fail-first coverage so any future
"silent" semantics change of an existing field fails a test.
"""

from decimal import Decimal

import pytest

from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit, VisitService

pytestmark = pytest.mark.integration


def _make_visit(db_session, patient, amount, *, status="open"):
    visit = Visit(patient_id=patient.id, status=status, discount_mode="none")
    db_session.add(visit)
    db_session.flush()
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=1,
            name="SYNTHETIC-csh-fe-036",
            qty=1,
            price=amount,
        )
    )
    db_session.commit()
    return visit


def _make_paid_payment(db_session, visit, amount, *, method="cash"):
    payment = Payment(
        visit_id=visit.id,
        amount=Decimal(str(amount)),
        method=method,
        status="paid",
    )
    db_session.add(payment)
    db_session.commit()
    return payment


def _refund(client, headers, payment_id, amount):
    response = client.post(
        f"/api/v1/cashier/payments/{payment_id}/refund",
        headers=headers,
        json={"amount": amount, "reason": "SYNTHETIC-csh-fe-036 refund"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _stats(client, headers):
    response = client.get("/api/v1/cashier/stats", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _dec(value) -> Decimal:
    return Decimal(str(value))


def _fm_deposit_credit(db_session, *, patient_id, payment_id, visit_id, amount, performed_by):
    """Real force-majeure leg (PR #3830 review): the exact path
    ``ForceMajeureService.cancel_entries_with_refund`` takes for
    ``RefundType.DEPOSIT`` — inserts a ``DepositTransaction`` CREDIT and
    never touches ``Payment.refunded_amount``.
    """
    from app.services.force_majeure_service import ForceMajeureService

    result = ForceMajeureService(db_session)._add_to_deposit(
        patient_id=patient_id,
        amount=amount,
        reason="SYNTHETIC-csh-fe-036 fm deposit credit",
        payment_id=payment_id,
        visit_id=visit_id,
        performed_by_id=performed_by,
    )
    db_session.commit()
    return result


def _fm_bank_request(db_session, *, patient_id, payment_id, visit_id, amount):
    """Real force-majeure leg (PR #3830 review): the automatic bank-transfer
    claim ``ForceMajeureService._create_refund_request`` creates — born
    ``pending`` with a ``payment_refund_claims`` row, like a live
    ``cancel_entries_with_refund`` bank leg."""
    from app.models.refund_deposit import RefundType
    from app.services.force_majeure_service import ForceMajeureService

    result = ForceMajeureService(db_session)._create_refund_request(
        patient_id=patient_id,
        payment_id=payment_id,
        visit_id=visit_id,
        amount=amount,
        reason="SYNTHETIC-csh-fe-036 fm bank request",
        refund_type=RefundType.BANK_TRANSFER,
        is_automatic=True,
    )
    db_session.commit()
    return result


def test_partial_refund_keeps_gross_and_adds_net(
    client, db_session, test_patient, admin_auth_headers
):
    """paid 100 000 cash + partial refund 30 000.

    Gross stays 100 000 (existing fields unchanged); refunded_amount 30 000;
    net 70 000 for both total and cash; pending debt is net as well.
    """
    visit = _make_visit(db_session, test_patient, 100000)
    payment = _make_paid_payment(db_session, visit, 100000, method="cash")
    _refund(client, admin_auth_headers, payment.id, 30000)

    stats = _stats(client, admin_auth_headers)

    # Existing contract (gross) — unchanged by this fix.
    assert _dec(stats["total_amount"]) == Decimal("100000")
    assert _dec(stats["cash_amount"]) == Decimal("100000")
    assert _dec(stats["card_amount"]) == Decimal("0")
    # New net-of-refunds contract.
    assert _dec(stats["refunded_amount"]) == Decimal("30000")
    assert _dec(stats["net_total_amount"]) == Decimal("70000")
    assert _dec(stats["net_cash_amount"]) == Decimal("70000")
    assert _dec(stats["net_card_amount"]) == Decimal("0")
    # pending debt is net of refunds (CSH-FE-028): 100 000 visit, 70 000 net.
    assert _dec(stats["pending_amount"]) == Decimal("30000")
    assert stats["pending_count"] == 1


def test_card_payment_net_split_by_method(
    client, db_session, test_patient, admin_auth_headers
):
    """A card payment without refunds: net fields mirror the gross ones."""
    visit = _make_visit(db_session, test_patient, 50000)
    _make_paid_payment(db_session, visit, 50000, method="card")

    stats = _stats(client, admin_auth_headers)

    assert _dec(stats["refunded_amount"]) == Decimal("0")
    assert _dec(stats["net_total_amount"]) == Decimal("50000")
    assert _dec(stats["net_cash_amount"]) == Decimal("0")
    assert _dec(stats["net_card_amount"]) == Decimal("50000")


def test_fully_refunded_payment_leaves_gross_and_net(
    client, db_session, test_patient, admin_auth_headers
):
    """A FULL refund flips the status to 'refunded': the payment leaves the
    paid set entirely — it never entered the gross sums, so neither
    refunded_amount nor the net fields may count it. cancelled_count grows.
    """
    visit = _make_visit(db_session, test_patient, 80000)
    payment = _make_paid_payment(db_session, visit, 80000, method="cash")
    _refund(client, admin_auth_headers, payment.id, 80000)

    stats = _stats(client, admin_auth_headers)

    assert _dec(stats["total_amount"]) == Decimal("0")
    assert _dec(stats["cash_amount"]) == Decimal("0")
    assert _dec(stats["refunded_amount"]) == Decimal("0")
    assert _dec(stats["net_total_amount"]) == Decimal("0")
    assert _dec(stats["net_cash_amount"]) == Decimal("0")
    assert _dec(stats["net_card_amount"]) == Decimal("0")
    assert stats["cancelled_count"] >= 1
    # The visit debt reopens fully (net paid is 0) — CSH-FE-028 semantics.
    assert _dec(stats["pending_amount"]) == Decimal("80000")
    assert stats["pending_count"] == 1


def test_mixed_cash_and_card_partial_refunds_split_nets_by_method(
    client, db_session, test_patient, admin_auth_headers
):
    """cash 60 000 (refund 20 000) + card 40 000 (no refund):

    gross: total 100 000 / cash 60 000 / card 40 000;
    net:   total  80 000 / cash 40 000 / card 40 000.
    """
    patient = test_patient
    visit_a = _make_visit(db_session, patient, 60000)
    payment_a = _make_paid_payment(db_session, visit_a, 60000, method="cash")
    _refund(client, admin_auth_headers, payment_a.id, 20000)

    visit_b = _make_visit(db_session, patient, 40000)
    _make_paid_payment(db_session, visit_b, 40000, method="card")

    stats = _stats(client, admin_auth_headers)

    assert _dec(stats["total_amount"]) == Decimal("100000")
    assert _dec(stats["cash_amount"]) == Decimal("60000")
    assert _dec(stats["card_amount"]) == Decimal("40000")
    assert _dec(stats["refunded_amount"]) == Decimal("20000")
    assert _dec(stats["net_total_amount"]) == Decimal("80000")
    assert _dec(stats["net_cash_amount"]) == Decimal("40000")
    assert _dec(stats["net_card_amount"]) == Decimal("40000")


def test_fm_deposit_credit_is_a_completed_refund_for_net_stats(
    client, db_session, test_patient, admin_user, admin_auth_headers
):
    """PR #3830 review P1: a force-majeure deposit credit returns money
    WITHOUT touching ``Payment.refunded_amount`` (only a
    ``DepositTransaction`` CREDIT row + the patient balance rise). Next to an
    ordinary paid payment, stats must recognize the completed refund:
    ``refunded_amount`` grows and net receipts drop; gross fields stay
    untouched."""
    visit_plain = _make_visit(db_session, test_patient, 100000)
    _make_paid_payment(db_session, visit_plain, 100000, method="cash")

    visit_fm = _make_visit(db_session, test_patient, 100000)
    payment_fm = _make_paid_payment(db_session, visit_fm, 100000, method="card")
    credit = _fm_deposit_credit(
        db_session,
        patient_id=test_patient.id,
        payment_id=payment_fm.id,
        visit_id=visit_fm.id,
        amount=100000,
        performed_by=admin_user.id,
    )
    assert credit.get("already_refunded") is not True

    # The FM leg really leaves the payment column untouched.
    db_session.refresh(payment_fm)
    assert payment_fm.status == "paid"
    assert not payment_fm.refunded_amount

    stats = _stats(client, admin_auth_headers)

    # Gross contract is untouched by the FM leg.
    assert _dec(stats["total_amount"]) == Decimal("200000")
    assert _dec(stats["cash_amount"]) == Decimal("100000")
    assert _dec(stats["card_amount"]) == Decimal("100000")
    # Net contract recognizes the completed deposit refund.
    assert _dec(stats["refunded_amount"]) == Decimal("100000")
    assert _dec(stats["net_total_amount"]) == Decimal("100000")
    assert _dec(stats["net_cash_amount"]) == Decimal("100000")
    assert _dec(stats["net_card_amount"]) == Decimal("0")
    # Pending semantics (CSH-FE-028) are not changed by this fix.
    assert _dec(stats["pending_amount"]) == Decimal("0")
    assert stats["pending_count"] == 0


def test_completed_bank_request_nets_and_pending_one_does_not(
    client, db_session, test_patient, admin_auth_headers
):
    """PR #3830 review P1: only a COMPLETED bank refund request returned the
    money (``RefundRequest.status == 'completed'`` — the single change the
    FM API 'complete' action makes); a still-pending request has sent
    nothing yet and must not reduce net receipts."""
    from app.models.refund_deposit import RefundRequest as RefundRequestRow
    from app.models.refund_deposit import RefundRequestStatus

    visit_done = _make_visit(db_session, test_patient, 100000)
    payment_done = _make_paid_payment(db_session, visit_done, 100000, method="card")
    _fm_bank_request(
        db_session,
        patient_id=test_patient.id,
        payment_id=payment_done.id,
        visit_id=visit_done.id,
        amount=100000,
    )
    # Exactly what force_majeure_api_service 'complete' does: status only.
    request_done = (
        db_session.query(RefundRequestRow).filter_by(payment_id=payment_done.id).one()
    )
    request_done.status = RefundRequestStatus.COMPLETED.value
    db_session.commit()

    visit_wait = _make_visit(db_session, test_patient, 60000)
    payment_wait = _make_paid_payment(db_session, visit_wait, 60000, method="cash")
    _fm_bank_request(
        db_session,
        patient_id=test_patient.id,
        payment_id=payment_wait.id,
        visit_id=visit_wait.id,
        amount=60000,
    )  # stays pending — money not sent yet

    stats = _stats(client, admin_auth_headers)

    assert _dec(stats["total_amount"]) == Decimal("160000")
    # Completed bank claim counts; the pending one does not.
    assert _dec(stats["refunded_amount"]) == Decimal("100000")
    assert _dec(stats["net_total_amount"]) == Decimal("60000")
    assert _dec(stats["net_card_amount"]) == Decimal("0")
    assert _dec(stats["net_cash_amount"]) == Decimal("60000")


def test_over_refunded_payment_caps_net_at_zero(
    client, db_session, test_patient, admin_user, admin_auth_headers
):
    """Anomaly guard (parity with ``PaymentInvariantService.
    _net_settled_amount``): a 100 000 payment with a 30 000 direct partial
    refund and a full FM deposit credit (the FM leg credits
    ``payment.amount``) must not push net receipts below zero — the payment
    contributes exactly 0 net, never a negative one."""
    visit = _make_visit(db_session, test_patient, 100000)
    payment = _make_paid_payment(db_session, visit, 100000, method="cash")
    _refund(client, admin_auth_headers, payment.id, 30000)
    _fm_deposit_credit(
        db_session,
        patient_id=test_patient.id,
        payment_id=payment.id,
        visit_id=visit.id,
        amount=100000,
        performed_by=admin_user.id,
    )

    stats = _stats(client, admin_auth_headers)

    assert _dec(stats["total_amount"]) == Decimal("100000")
    # 30 000 direct + 100 000 deposit credit would be 130 000 — capped at
    # the payment's unrefunded remainder (100 000 total effective refund).
    assert _dec(stats["refunded_amount"]) == Decimal("100000")
    assert _dec(stats["net_total_amount"]) == Decimal("0")
    assert _dec(stats["net_cash_amount"]) == Decimal("0")


def test_openapi_documents_gross_and_net_fields(client: object = None) -> None:
    """The response schema must document both semantics (OpenAPI contract)."""
    from app.api.v1.endpoints.cashier._helpers import CashierStatsResponse

    fields = CashierStatsResponse.model_fields
    for name in (
        "total_amount",
        "cash_amount",
        "card_amount",
        "refunded_amount",
        "net_total_amount",
        "net_cash_amount",
        "net_card_amount",
        "pending_amount",
    ):
        assert name in fields, f"missing stats field: {name}"
        assert fields[name].description, f"missing description for {name}"

    gross_doc = fields["total_amount"].description or ""
    net_doc = fields["net_total_amount"].description or ""
    assert "БЕЗ вычета возвратов" in gross_doc
    assert "за вычетом возвратов" in net_doc

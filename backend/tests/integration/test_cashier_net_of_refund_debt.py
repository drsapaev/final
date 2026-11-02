"""CSH-FE-028: cashier debt readers must agree with canonical net settled amounts.

Fail-first coverage for the cashier audit finding: ``get_pending_payments``,
``get_cashier_stats`` and grouped payment allocation summed gross
``Payment.amount`` for ``paid``/``completed`` payments and ignored
``refunded_amount``, while the canonical ``PaymentInvariantService`` computes
net ``max(amount - refunded_amount, 0)``. After a partial refund of 70 000
from a paid 100 000 visit the cashier readers must report due 70 000 —
the same number as ``PaymentInvariantService.compute_paid_amount`` implies.
"""

from decimal import Decimal

import pytest

from app.models.patient import Patient
from app.models.payment import Payment
from app.models.visit import Visit, VisitService
from app.services.payment_invariant_service import PaymentInvariantService

pytestmark = pytest.mark.integration


def _make_visit(db_session, patient, amount, *, status="open"):
    visit = Visit(patient_id=patient.id, status=status, discount_mode="none")
    db_session.add(visit)
    db_session.flush()
    db_session.add(
        VisitService(
            visit_id=visit.id,
            service_id=1,
            name="SYNTHETIC-csh-fe-028",
            qty=1,
            price=amount,
        )
    )
    db_session.commit()
    return visit


def _make_paid_payment(db_session, visit, amount):
    payment = Payment(
        visit_id=visit.id,
        amount=Decimal(str(amount)),
        method="cash",
        status="paid",
    )
    db_session.add(payment)
    db_session.commit()
    return payment


def _refund(client, headers, payment_id, amount):
    response = client.post(
        f"/api/v1/cashier/payments/{payment_id}/refund",
        headers=headers,
        json={"amount": amount, "reason": "SYNTHETIC-csh-fe-028 partial refund"},
    )
    assert response.status_code == 200, response.text
    return response.json()


def _pending_groups(client, headers):
    response = client.get("/api/v1/cashier/pending-payments", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _group_for(groups, patient_id):
    matched = [g for g in groups if g["patient_id"] == patient_id]
    assert len(matched) == 1, f"expected one pending group, got {matched}"
    return matched[0]


def _stats(client, headers):
    response = client.get("/api/v1/cashier/stats", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture
def single_visit_world(db_session, test_patient):
    """One patient, one visit (100 000) fully paid by a single payment."""
    visit = _make_visit(db_session, test_patient, 100000)
    payment = _make_paid_payment(db_session, visit, 100000)
    return {"patient": test_patient, "visit": visit, "payment": payment}


@pytest.fixture
def grouped_world(db_session):
    """Dedicated patient with two visits: A 100 000 paid then partially
    refunded 70 000 (net 30 000, due 70 000) and B 50 000 unpaid."""
    patient = Patient(
        first_name="Группа",
        last_name="Пациентов",
        phone="+998900000042",
    )
    db_session.add(patient)
    db_session.commit()
    visit_a = _make_visit(db_session, patient, 100000)
    visit_b = _make_visit(db_session, patient, 50000)
    payment = _make_paid_payment(db_session, visit_a, 100000)
    return {
        "patient": patient,
        "visit_a": visit_a,
        "visit_b": visit_b,
        "payment": payment,
    }


def test_pending_list_reports_net_debt_after_partial_refund(
    client, db_session, admin_auth_headers, single_visit_world
):
    world = single_visit_world
    _refund(client, admin_auth_headers, world["payment"].id, 70000)

    groups = _pending_groups(client, admin_auth_headers)
    group = _group_for(groups, world["patient"].id)

    assert Decimal(str(group["paid_amount"])) == Decimal("30000")
    assert Decimal(str(group["remaining_amount"])) == Decimal("70000")
    assert group["status"] == "partial"

    # Agreement with the canonical invariant service.
    canonical_paid = PaymentInvariantService(db_session).compute_paid_amount(
        world["visit"].id
    )
    assert canonical_paid == Decimal("30000")
    assert Decimal(str(group["total_amount"])) - canonical_paid == Decimal("70000")


def test_stats_report_net_pending_debt_after_partial_refund(
    client, db_session, admin_auth_headers, single_visit_world
):
    world = single_visit_world
    _refund(client, admin_auth_headers, world["payment"].id, 70000)

    stats = _stats(client, admin_auth_headers)
    assert stats["pending_count"] == 1
    assert Decimal(str(stats["pending_amount"])) == Decimal("70000")


def test_grouped_allocation_covers_refunded_debt_across_mixed_visits(
    client, db_session, admin_auth_headers, grouped_world
):
    world = grouped_world
    _refund(client, admin_auth_headers, world["payment"].id, 70000)

    # Pending group merges both visits: 150 000 total, 30 000 net paid,
    # 120 000 remaining.
    groups = _pending_groups(client, admin_auth_headers)
    group = _group_for(groups, world["patient"].id)
    assert Decimal(str(group["total_amount"])) == Decimal("150000")
    assert Decimal(str(group["paid_amount"])) == Decimal("30000")
    assert Decimal(str(group["remaining_amount"])) == Decimal("120000")

    response = client.post(
        "/api/v1/cashier/payments/grouped",
        headers=admin_auth_headers,
        json={
            "visit_ids": [world["visit_a"].id, world["visit_b"].id],
            "amount": 120000,
            "method": "cash",
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()

    allocations = {
        item["visit_id"]: Decimal(str(item["amount"]))
        for item in payload["allocations"]
    }
    assert allocations[world["visit_a"].id] == Decimal("70000")
    assert allocations[world["visit_b"].id] == Decimal("50000")

    db_session.expire_all()
    payment_amounts = sorted(
        Decimal(str(row[0]))
        for row in db_session.query(Payment.amount).filter(
            Payment.status.in_(["paid", "completed"])
        ).all()
    )
    # 100 000 (original) + grouped 70 000 + 50 000.
    assert payment_amounts == [
        Decimal("50000"),
        Decimal("70000"),
        Decimal("100000"),
    ]

    # The patient leaves the pending list — debt fully covered.
    remaining_groups = _pending_groups(client, admin_auth_headers)
    assert all(g["patient_id"] != world["patient"].id for g in remaining_groups)


def test_fully_refunded_visit_keeps_full_debt(
    client, db_session, admin_auth_headers, single_visit_world
):
    world = single_visit_world
    _refund(client, admin_auth_headers, world["payment"].id, 100000)

    groups = _pending_groups(client, admin_auth_headers)
    group = _group_for(groups, world["patient"].id)
    assert Decimal(str(group["paid_amount"])) == Decimal("0")
    assert Decimal(str(group["remaining_amount"])) == Decimal("100000")
    assert group["status"] == "pending"

    stats = _stats(client, admin_auth_headers)
    assert stats["pending_count"] == 1
    assert Decimal(str(stats["pending_amount"])) == Decimal("100000")

    canonical_paid = PaymentInvariantService(db_session).compute_paid_amount(
        world["visit"].id
    )
    assert canonical_paid == Decimal("0")


def test_single_visit_top_up_after_partial_refund_is_allowed(
    client, db_session, admin_auth_headers, single_visit_world
):
    """The single-visit payment path already uses the canonical net amount.

    Locks the contract so the re-opened 70 000 debt stays payable through
    the direct payment endpoint while the list readers are fixed.
    """
    world = single_visit_world
    _refund(client, admin_auth_headers, world["payment"].id, 70000)

    response = client.post(
        "/api/v1/cashier/payments",
        headers=admin_auth_headers,
        json={
            "visit_id": world["visit"].id,
            "amount": 70000,
            "method": "cash",
        },
    )
    assert response.status_code == 200, response.text

    canonical_paid = PaymentInvariantService(db_session).compute_paid_amount(
        world["visit"].id
    )
    assert canonical_paid == Decimal("100000")

    groups = _pending_groups(client, admin_auth_headers)
    assert all(g["patient_id"] != world["patient"].id for g in groups)

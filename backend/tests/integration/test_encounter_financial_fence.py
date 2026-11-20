"""Purely synthetic snapshot/requote tests; production fencing is separate."""

from datetime import date
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from app.models.all_free_request import AllFreeRequest
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    lock_financial_group,
    lock_group_without_pending,
    requote_draft_invoices,
    requote_draft_invoice_prices,
)
from tests.integration.test_encounter_migration_pg import _migration


@pytest.fixture
def group(db_session):
    patient = Patient(first_name="SYNTHETIC", last_name="Finance")
    service = Service(code="SYNTHETIC-FINANCE", name="SYNTHETIC", price=Decimal("0.07"), active=True)
    db_session.add_all([patient, service])
    db_session.flush()
    encounter = Encounter(patient_id=patient.id, provenance="new")
    db_session.add(encounter)
    db_session.flush()
    visits = [Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1), status="pending_confirmation") for _ in range(2)]
    db_session.add_all(visits)
    db_session.flush()
    db_session.add_all([
        VisitService(visit_id=visits[0].id, service_id=service.id, name="SYNTHETIC", qty=3, price=Decimal("0.07"), currency="UZS"),
        VisitService(visit_id=visits[1].id, service_id=service.id, name="SYNTHETIC", qty=1, price=Decimal("0.00"), currency="UZS"),
    ])
    invoice = PaymentInvoice(patient_id=patient.id, total_amount=Decimal("0.21"), status="pending", payment_method="cash", currency="UZS")
    db_session.add(invoice)
    db_session.flush()
    links = [PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visits[0].id, visit_amount=Decimal("0.21")),
             PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visits[1].id, visit_amount=Decimal("0.00"))]
    db_session.add_all(links)
    db_session.flush()
    return visits, invoice, links


def test_requote_preserves_exact_quantity_and_zero_link(db_session, group):
    visits, invoice, links = group
    locked = lock_financial_group(db_session, visits[0].id)
    assert locked.gross_by_visit == {visits[0].id: Decimal("0.21"), visits[1].id: Decimal("0.00")}
    requote_draft_invoices(locked, {visits[0].id: Decimal("0.11"), visits[1].id: Decimal("0.00")})
    db_session.flush()
    assert invoice.total_amount == Decimal("0.11")
    assert [line.visit_amount for line in links] == [Decimal("0.11"), Decimal("0.00")]


def test_cross_encounter_invoice_preserves_other_group_amount(db_session, group):
    visits, invoice, _ = group
    original_line = db_session.query(VisitService).filter_by(visit_id=visits[0].id).one()
    other_encounter = Encounter(patient_id=visits[0].patient_id, provenance="new")
    db_session.add(other_encounter)
    db_session.flush()
    other = Visit(patient_id=visits[0].patient_id, encounter_id=other_encounter.id,
                  status="pending_confirmation", confirmation_context_epoch=1)
    db_session.add(other)
    db_session.flush()
    db_session.add(VisitService(visit_id=other.id, service_id=original_line.service_id,
                                name="SYNTHETIC", qty=1, price=Decimal("0.05"), currency="UZS"))
    link = PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=other.id, visit_amount=Decimal("0.05"))
    db_session.add(link)
    invoice.total_amount = Decimal("0.26")
    db_session.flush()
    locked = lock_financial_group(db_session, visits[0].id)
    assert {v.id for v in locked.visits} == {v.id for v in visits}
    requote_draft_invoices(locked, {visits[0].id: Decimal("0.11"), visits[1].id: Decimal("0.00")})
    db_session.flush()
    assert invoice.total_amount == Decimal("0.16")
    assert link.visit_amount == Decimal("0.05")


def test_equal_aggregate_does_not_hide_stale_allocation(db_session, group):
    visits, invoice, links = group
    # Equal invoice aggregate, but one visit became stale and another absorbed it.
    links[0].visit_amount = Decimal("0.20")
    links[1].visit_amount = Decimal("0.01")
    db_session.flush()
    with pytest.raises(FinancialFenceError, match="Распределение"):
        lock_financial_group(db_session, visits[0].id)
    assert invoice.total_amount == Decimal("0.21")


@pytest.mark.parametrize("status", ["paid", "processing", "failed", "cancelled"])
def test_provider_payment_requires_reconciliation(db_session, group, status):
    visits, invoice, _ = group
    db_session.add(Payment(visit_id=visits[0].id, amount=Decimal("0.21"), currency="UZS", method="online", provider="click", status=status))
    db_session.flush()
    with pytest.raises(FinancialFenceError, match="Платежи"):
        lock_financial_group(db_session, visits[0].id)
    assert invoice.total_amount == Decimal("0.21")


def test_invalid_requote_does_not_partially_change_invoice(db_session, group):
    visits, invoice, links = group
    locked = lock_financial_group(db_session, visits[0].id)
    with pytest.raises(FinancialFenceError):
        requote_draft_invoices(locked, {visits[0].id: Decimal("0.11"), visits[1].id: Decimal("0.01")})
    assert invoice.total_amount == Decimal("0.21")
    assert [line.visit_amount for line in links] == [Decimal("0.21"), Decimal("0.00")]


def test_reprice_allows_exact_increase_but_requires_unchanged_baseline(db_session, group):
    visits, invoice, links = group
    locked = lock_financial_group(db_session, visits[0].id)
    requote_draft_invoice_prices(locked, {visits[0].id: Decimal("0.31"), visits[1].id: Decimal("0.00")})
    assert invoice.total_amount == Decimal("0.31")
    assert [link.visit_amount for link in links] == [Decimal("0.31"), Decimal("0.00")]
    # Reusing a snapshot after it has already rewritten the invoice is denied.
    with pytest.raises(FinancialFenceError, match="после проверки"):
        requote_draft_invoice_prices(locked, {visits[0].id: Decimal("0.41"), visits[1].id: Decimal("0.00")})


def test_reprice_does_not_override_approved_all_free(db_session, group):
    visits, invoice, _ = group
    request = AllFreeRequest(visit_id=visits[0].id, patient_id=visits[0].patient_id, encounter_id=visits[0].encounter_id,
        visit_id_snapshot=visits[0].id, patient_id_snapshot=visits[0].patient_id, encounter_id_snapshot=visits[0].encounter_id,
        visit_context_epoch=1, baseline_total=Decimal("0.21"), status="approved", requested_by_user_id_snapshot=1,
        requested_by_role_snapshot="admin", policy_auto_approve=False, decision_kind="admin",
        decided_by_user_id_snapshot=1, decided_by_role_snapshot="admin", decided_at=datetime.now(UTC))
    db_session.add(request)
    db_session.flush()
    locked = lock_financial_group(db_session, visits[0].id)
    with pytest.raises(FinancialFenceError, match="администратора"):
        requote_draft_invoice_prices(locked, {visits[0].id: Decimal("0.31"), visits[1].id: Decimal("0.00")})
    assert invoice.total_amount == Decimal("0.21")


def test_sibling_pending_is_visible_and_never_authorizes_payment(db_session, group):
    visits, _, _ = group
    def request_for(visit):
        return AllFreeRequest(
            visit_id=visit.id, patient_id=visit.patient_id, encounter_id=visit.encounter_id,
            visit_id_snapshot=visit.id, patient_id_snapshot=visit.patient_id,
            encounter_id_snapshot=visit.encounter_id, visit_context_epoch=1,
            baseline_total=Decimal("0.21"), status="pending", requested_by_user_id_snapshot=1,
            requested_by_role_snapshot="admin", policy_auto_approve=False,
        )
    first = request_for(visits[0])
    db_session.add(first)
    db_session.flush()
    batch = lock_financial_group(db_session, visits[1].id, allow_sibling_pending_for_staging=True)
    assert [r.id for r in batch.pending_requests] == [first.id]
    with pytest.raises(FinancialFenceError):
        lock_financial_group(db_session, visits[1].id)
    second = request_for(visits[1])
    db_session.add(second)
    db_session.flush()
    decision = lock_financial_group(db_session, visits[0].id, allow_all_free_request_id=first.id)
    assert {r.id for r in decision.pending_requests} == {first.id, second.id}
    with pytest.raises(FinancialFenceError):
        lock_financial_group(db_session, visits[1].id, allow_all_free_request_id=first.id)
    with pytest.raises(FinancialFenceError):
        lock_financial_group(db_session, visits[1].id, allow_sibling_pending_for_staging=True)
    with pytest.raises(FinancialFenceError, match="заявка"):
        lock_group_without_pending(db_session, visits[0].id)
    first.status = "invalidated"
    db_session.flush()
    with pytest.raises(FinancialFenceError, match="заявка"):
        lock_group_without_pending(db_session, visits[0].id)
    second.status = "invalidated"
    db_session.add(Payment(visit_id=visits[0].id, amount=Decimal("0.05"), status="paid", method="cash", currency="UZS"))
    db_session.flush()
    lock_group_without_pending(db_session, visits[0].id)


@pytest.mark.parametrize("recursive", [0, 1])
def test_sqlite_generation_survives_downgrade_and_reused_id(recursive):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.execute(text(f"PRAGMA recursive_triggers={recursive}"))
            conn.execute(text("CREATE TABLE encounters (id INTEGER PRIMARY KEY, patient_id INTEGER, generation INTEGER NOT NULL DEFAULT 1)"))
            conn.execute(text("CREATE TABLE visits (id INTEGER PRIMARY KEY, patient_id INTEGER, encounter_id INTEGER)"))
            conn.execute(text("INSERT INTO encounters VALUES (1,1,5000000000000000)"))
            conn.execute(text("INSERT INTO visits VALUES (1,1,1)"))
            migration = _migration("0118_encounter_financial_fence.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            assert conn.execute(text("SELECT generation FROM encounters WHERE id=1")).scalar_one() == 5000000000000000
            conn.execute(text("INSERT INTO visits VALUES (2,1,1)"))
            changed = conn.execute(text("SELECT generation FROM encounters WHERE id=1")).scalar_one()
            assert changed > 5000000000000000
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text("UPDATE encounters SET generation=5000000000000000 WHERE id=1"))
            conn.execute(text("INSERT INTO encounters (id,patient_id) VALUES (2,1)"))
            first = conn.execute(text("SELECT generation FROM encounters WHERE id=2")).scalar_one()
            conn.execute(text("DELETE FROM encounters WHERE id=2"))
            migration.downgrade()
            migration.upgrade()
            conn.execute(text("INSERT INTO encounters (id,patient_id) VALUES (2,1)"))
            assert conn.execute(text("SELECT generation FROM encounters WHERE id=2")).scalar_one() > first
    finally:
        engine.dispose()

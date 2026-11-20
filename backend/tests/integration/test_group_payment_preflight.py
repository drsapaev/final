"""Group preflight uses one transaction and rejects stale savepoint markers."""

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.base_class import Base
from app.models.all_free_request import AllFreeRequest
from app.models.click_callback_receipt import (
    ClickCallbackReceipt,
    ClickReceiptKeyVersion,
)
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    acquire_reconciliation_mutex,
    preflight_payment_groups,
)
from app.services.payment_invariant_service import PaymentInvariantService
from tests.synthetic_reconciliation import install_reconciliation_fence


@pytest.fixture
def case(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'synthetic.sqlite'}")
    Base.metadata.create_all(engine)
    install_reconciliation_fence(engine)
    with Session(engine, expire_on_commit=False) as db:
        patient = Patient(first_name="SYNTHETIC", last_name="Preflight")
        service = Service(code="SYNTHETIC-PREFLIGHT", name="SYNTHETIC", price=Decimal("1.00"), active=True)
        db.add_all([patient, service])
        db.flush()
        encounters = [Encounter(patient_id=patient.id, provenance="new") for _ in range(2)]
        db.add_all(encounters)
        db.flush()
        visits = [Visit(patient_id=patient.id, encounter_id=encounters[index % 2].id,
                        visit_date=date(2099, 1, 1), status="pending_confirmation",
                        confirmation_context_epoch=1) for index in range(4)]
        db.add_all(visits)
        db.flush()
        db.add_all([VisitService(visit_id=v.id, service_id=service.id, name="SYNTHETIC",
                                 qty=2, price=Decimal("1.00"), currency="UZS") for v in visits])
        db.commit()
        ids = [v.id for v in visits]
        yield db, ids
    engine.dispose()


def _pending(db, visit_id):
    visit = db.get(Visit, visit_id)
    request = AllFreeRequest(visit_id=visit.id, patient_id=visit.patient_id, encounter_id=visit.encounter_id,
        visit_id_snapshot=visit.id, patient_id_snapshot=visit.patient_id, encounter_id_snapshot=visit.encounter_id,
        visit_context_epoch=1, baseline_total=Decimal("2.00"), status="pending", requested_by_user_id_snapshot=1,
        requested_by_role_snapshot="admin", policy_auto_approve=False)
    db.add(request)
    db.flush()
    return request


def test_preflight_union_supports_multiple_groups_and_partial_payments(case):
    db, ids = case
    preflight_payment_groups(db, ids[:2])
    service = PaymentInvariantService(db)
    for visit_id in ids:
        service.create_payment_for_visit(visit_id, Decimal("0.25"), "cash", None,
                                         SimpleNamespace(id=1), commit=False)
    assert db.query(Payment).count() == 4
    db.commit()


def test_preflight_checks_pending_on_sibling_visit_and_rolls_back(case):
    db, ids = case
    _pending(db, ids[2])
    db.commit()
    with pytest.raises(HTTPException) as error:
        PaymentInvariantService(db).create_payment_for_visit(
            ids[0], Decimal("0.25"), "cash", None, SimpleNamespace(id=1), commit=False
        )
    assert error.value.status_code == 409
    assert db.query(Payment).count() == 0


def test_zero_invoice_link_closes_over_other_encounter(case):
    db, ids = case
    first, second = db.get(Visit, ids[0]), db.get(Visit, ids[1])
    invoice = PaymentInvoice(patient_id=first.patient_id, total_amount=Decimal("2.00"), status="pending", currency="UZS")
    db.add(invoice)
    db.flush()
    db.add_all([PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=first.id, visit_amount=Decimal("2.00")),
                PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=second.id, visit_amount=Decimal("0.00"))])
    db.commit()
    preflight_payment_groups(db, [ids[0]])
    # ids[3] belongs to the encounter pulled in through the zero link.
    preflight_payment_groups(db, [ids[3]])
    db.rollback()
    _pending(db, ids[3])
    db.commit()
    with pytest.raises(FinancialFenceError, match="заявка"):
        preflight_payment_groups(db, [ids[0]])


def test_complete_receipt_requires_reconciliation_before_payment(case):
    db, ids = case
    assert acquire_reconciliation_mutex(db, None) is False
    db.rollback()
    db.add(ClickReceiptKeyVersion(version="synthetic", commitment="a" * 64))
    db.flush()
    db.add(ClickCallbackReceipt(event_key="b" * 64, body_digest="c" * 64, variant_slot=0,
        phase="complete", confidence="authenticated", media_type="application/json", body_size=1,
        key_version="synthetic", ciphertext=b"synthetic-ciphertext"))
    db.commit()
    assert acquire_reconciliation_mutex(db, None) is True
    db.rollback()
    with pytest.raises(FinancialFenceError, match="сверки"):
        preflight_payment_groups(db, [ids[0]])


def test_marker_rechecks_context_and_cannot_extend_after_first_lock(case):
    db, ids = case
    preflight_payment_groups(db, [ids[0]])
    with pytest.raises(FinancialFenceError, match="Все визиты"):
        preflight_payment_groups(db, [ids[1]])
    db.rollback()
    preflight_payment_groups(db, [ids[0]])
    line = db.query(VisitService).filter_by(visit_id=ids[0]).one()
    line.price = Decimal("0.50")
    with pytest.raises(FinancialFenceError, match="изменения"):
        preflight_payment_groups(db, [ids[0]])
    db.rollback()


@pytest.mark.parametrize("savepoint_kind", ["session", "connection"])
@pytest.mark.parametrize("finish", ["rollback", "commit"])
def test_marker_invalidated_when_savepoint_changes(case, savepoint_kind, finish):
    db, ids = case
    db.connection()
    savepoint = db.begin_nested() if savepoint_kind == "session" else db.connection().begin_nested()
    preflight_payment_groups(db, [ids[0]])
    getattr(savepoint, finish)()
    with pytest.raises(FinancialFenceError, match="Транзакция"):
        preflight_payment_groups(db, [ids[0]])
    db.rollback()


def test_root_commit_invalidates_old_marker_and_new_pending_is_seen(case):
    db, ids = case
    preflight_payment_groups(db, [ids[0]])
    db.commit()
    _pending(db, ids[2])
    db.commit()
    with pytest.raises(FinancialFenceError, match="заявка"):
        preflight_payment_groups(db, [ids[0]])

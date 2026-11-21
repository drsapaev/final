"""Auto invoice uses a fenced visit snapshot; Float remains the read model."""
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.models.billing import BillingRule, BillingSettings, Invoice, InvoiceItem
from app.models.visit import VisitService
from app.services.billing_service import BillingService
from tests.integration.test_derma_price_override_integrity import (
    _create_doctor,
    _create_patient,
    _create_service,
    _create_user,
    _create_visit_with_service,
    _suffix,
)


@pytest.fixture
def case(db_session, monkeypatch):
    user = _create_user(db_session, role="derma", label="autobill")
    doctor = _create_doctor(db_session, user, specialty="dermatology")
    patient = _create_patient(db_session)
    service = _create_service(db_session, label=_suffix(), price=Decimal("99.00"))
    visit, line = _create_visit_with_service(db_session, patient=patient, doctor=doctor, service=service, price=Decimal("0.10"))
    line.qty = 3
    db_session.add(BillingRule(name="synthetic", is_active=True, trigger_event="visit_completed", priority=1, payment_terms_days=7, auto_send=True))
    db_session.commit()
    sender = Mock(return_value=True)
    monkeypatch.setattr(BillingService, "send_invoice", sender)
    return db_session, visit, line, service, sender


def test_snapshot_qty_and_cent_are_used_without_intermediate_commit(case):
    db, visit, line, _, sender = case
    from sqlalchemy import event

    commits = []
    event.listen(db, "after_commit", lambda _db: commits.append(True))
    invoice = BillingService(db).auto_generate_invoice_for_visit(visit.id)
    assert len(commits) == 1
    assert invoice.subtotal == 0.3
    assert invoice.total_amount == 0.3
    item = db.query(InvoiceItem).filter_by(invoice_id=invoice.id).one()
    assert item.quantity == 3
    assert item.unit_price == 0.1
    assert item.total_amount == 0.3
    assert item.description == line.name
    sender.assert_called_once_with(invoice.id)


def test_zero_price_is_not_replaced_by_catalog(case):
    db, visit, line, _, sender = case
    line.price = Decimal("0.00")
    db.commit()
    invoice = BillingService(db).auto_generate_invoice_for_visit(visit.id)
    item = db.query(InvoiceItem).filter_by(invoice_id=invoice.id).one()
    assert invoice.subtotal == invoice.total_amount == item.unit_price == item.total_amount == 0
    sender.assert_called_once()


@pytest.mark.parametrize("invalid", ["missing_price", "qty_zero", "missing_service", "fractional_tax", "overflow"])
def test_invalid_snapshot_rolls_back_invoice_and_sends_nothing(case, invalid):
    db, visit, line, service, sender = case
    if invalid == "missing_price":
        line.price = None
    elif invalid == "qty_zero":
        line.qty = 0
    elif invalid == "missing_service":
        line.service_id = service.id + 900000
    elif invalid == "overflow":
        line.qty = 2147483647
        line.price = Decimal("9999999999.99")
    else:
        line.qty = 1
        db.add(BillingSettings(default_tax_rate=5.0))
    db.commit()
    with pytest.raises(HTTPException) as error:
        BillingService(db).auto_generate_invoice_for_visit(visit.id)
    assert error.value.status_code == 409
    assert db.query(Invoice).filter_by(visit_id=visit.id).count() == 0
    sender.assert_not_called()


def test_all_items_come_from_the_visit_and_preserve_duplicate_rows(case):
    db, visit, line, _, _ = case
    second = VisitService(visit_id=visit.id, service_id=line.service_id, code=line.code,
                          name="Second synthetic line", qty=2, price=Decimal("0.20"))
    db.add(second)
    db.commit()
    invoice = BillingService(db).auto_generate_invoice_for_visit(visit.id)
    items = db.query(InvoiceItem).filter_by(invoice_id=invoice.id).order_by(InvoiceItem.id).all()
    assert len(items) == 2
    assert [item.quantity for item in items] == [3, 2]
    assert [item.unit_price for item in items] == [0.1, 0.2]
    assert invoice.total_amount == 0.7


def test_sqlite_busy_returns_409_and_same_session_can_retry(tmp_path, monkeypatch):
    from datetime import date

    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.db.base_class import Base
    from app.models.patient import Patient
    from app.models.service import Service
    from app.models.visit import Visit

    engine = create_engine(f"sqlite:///{tmp_path / 'billing.sqlite'}", connect_args={"timeout": 0.1})
    Base.metadata.create_all(engine)
    monkeypatch.setattr(BillingService, "send_invoice", Mock())
    try:
        with Session(engine, expire_on_commit=False) as db:
            patient = Patient(first_name="Synthetic", last_name="Invoice", birth_date=date(1990, 1, 1))
            service = Service(code="sqlite_bill", name="Synthetic", price=Decimal("10.00"), active=True)
            db.add_all([patient, service])
            db.flush()
            visit = Visit(patient_id=patient.id, visit_date=date(2099, 1, 1), status="open", source="desk")
            db.add(visit)
            db.flush()
            db.add_all([VisitService(visit_id=visit.id, service_id=service.id, name=service.name, qty=1, price=Decimal("10.00")),
                        BillingRule(name="synthetic", is_active=True, trigger_event="visit_completed", priority=1, payment_terms_days=7, auto_send=False)])
            visit_id = visit.id
            db.commit()
        with Session(engine) as writer, Session(engine, expire_on_commit=False) as issuer:
            line = writer.query(VisitService).filter_by(visit_id=visit_id).one()
            line.price = Decimal("6.00")
            writer.flush()
            with pytest.raises(HTTPException) as error:
                BillingService(issuer).auto_generate_invoice_for_visit(visit_id)
            assert error.value.status_code == 409
            writer.commit()
            invoice = BillingService(issuer).auto_generate_invoice_for_visit(visit_id)
            assert invoice.total_amount == 6.0
    finally:
        engine.dispose()


@pytest.mark.parametrize("dialect,sqlstate,sqlite_code,is_lock", [
    ("postgresql", "55P03", 0, True), ("postgresql", "40P01", 0, False),
    ("postgresql", "23505", 0, False), ("sqlite", None, 5, True),
    ("sqlite", None, 517, True), ("sqlite", None, 2067, False),
])
def test_only_real_lock_conflicts_are_translated(dialect, sqlstate, sqlite_code, is_lock):
    from types import SimpleNamespace

    from sqlalchemy.exc import DBAPIError

    class FakeSession:
        rolled_back = False

        def get_bind(self):
            return SimpleNamespace(dialect=SimpleNamespace(name=dialect))

        def execute(self, _):
            raise failure

        def query(self, *_):
            raise failure

        def rollback(self):
            self.rolled_back = True

    class Failure(Exception):
        pass

    original = Failure()
    original.sqlstate = sqlstate
    original.sqlite_errorcode = sqlite_code
    failure = DBAPIError("synthetic", {}, original)
    db = FakeSession()
    with pytest.raises(HTTPException if is_lock else DBAPIError) as error:
        BillingService(db).auto_generate_invoice_for_visit(1)
    assert db.rolled_back
    if is_lock:
        assert error.value.status_code == 409
    else:
        assert error.value is failure

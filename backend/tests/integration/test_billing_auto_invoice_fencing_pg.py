"""Synthetic PG barriers for billing auto-invoice creation."""
import threading
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from unittest.mock import Mock

import pytest
from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.orm import Session

from app.models.billing import BillingRule, BillingSettings, Invoice, InvoiceItem
from app.models.patient import Patient
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.billing_service import BillingService
from tests.integration.test_price_override_request_binding_pg import (  # noqa: F401
    _is_blocked,
    pg_case,
)


@pytest.fixture
def auto_case(pg_case, monkeypatch):
    engine, ids = pg_case
    with Session(engine) as db:
        db.add(BillingRule(name="Synthetic", is_active=True, trigger_event="visit_completed", priority=1, payment_terms_days=7, auto_send=True))
        db.commit()
    monkeypatch.setattr(BillingService, "send_invoice", Mock(return_value=True))
    return engine, ids


def _auto(engine, ids, ready=None, pids=None):
    with Session(engine, expire_on_commit=False) as db:
        if ready is not None:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
        try:
            invoice = BillingService(db).auto_generate_invoice_for_visit(ids["visit"])
            return 200, invoice.id
        except HTTPException as exc:
            return exc.status_code, None


def test_prior_child_change_is_visible_after_visit_lock(auto_case):
    engine, ids = auto_case
    ready, pids = threading.Event(), []
    with Session(engine) as editor:
        line = editor.get(VisitService, ids["line"])
        line.price = Decimal("7.25")
        line.qty = 2
        editor.flush()
        with ThreadPoolExecutor(max_workers=1) as pool:
            invoice = pool.submit(_auto, engine, ids, ready, pids)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                editor.commit()
            status, invoice_id = invoice.result(timeout=12)
    assert status == 200
    with Session(engine) as db:
        item = db.query(InvoiceItem).filter_by(invoice_id=invoice_id).one()
        assert item.unit_price == 7.25 and item.quantity == 2 and item.total_amount == 14.5


@pytest.mark.parametrize("mutation", ["price", "delete"])
def test_child_holding_row_and_waiting_visit_is_nowait_conflict(auto_case, mutation):
    engine, ids = auto_case
    locked, release, writer_done, pids = threading.Event(), threading.Event(), threading.Event(), []
    invoice_thread = []

    def pause_after_visit(_conn, _cursor, statement, _params, _context, _many):
        if threading.get_ident() in invoice_thread and "from visits" in statement.lower() and "for update" in statement.lower() and not locked.is_set():
            locked.set()
            if not release.wait(10):
                raise AssertionError("release timeout")

    def issue():
        invoice_thread.append(threading.get_ident())
        with Session(engine, expire_on_commit=False) as db:
            service = BillingService(db)
            with pytest.raises(HTTPException) as error:
                service.auto_generate_invoice_for_visit(ids["visit"])
            if not writer_done.wait(10):
                raise AssertionError("writer timeout")
            invoice = service.auto_generate_invoice_for_visit(ids["visit"])
            return error.value.status_code, invoice.id if invoice else None

    def mutate(ready):
        with Session(engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
            line = db.get(VisitService, ids["line"])
            if mutation == "delete":
                db.delete(line)
            else:
                line.price = Decimal("8.00")
            db.commit()

    event.listen(engine, "after_cursor_execute", pause_after_visit)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            issuer = pool.submit(issue)
            assert locked.wait(5)
            ready = threading.Event()
            writer = pool.submit(mutate, ready)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            try:
                writer.result(timeout=12)
            finally:
                writer_done.set()
            status, invoice_id = issuer.result(timeout=12)
        assert status == 409
        with Session(engine) as db:
            if mutation == "delete":
                assert invoice_id is None
                assert db.query(Invoice).count() == 0
            else:
                item = db.query(InvoiceItem).filter_by(invoice_id=invoice_id).one()
                assert item.unit_price == 8.0
    finally:
        release.set()
        writer_done.set()
        event.remove(engine, "after_cursor_execute", pause_after_visit)


def test_existing_line_update_waits_until_snapshot_commits(auto_case):
    engine, ids = auto_case
    locked, release, pids = threading.Event(), threading.Event(), []
    invoice_thread = []

    def pause_after_lines(_conn, _cursor, statement, _params, _context, _many):
        if threading.get_ident() in invoice_thread and "from visit_services" in statement.lower() and "for update" in statement.lower() and not locked.is_set():
            locked.set()
            if not release.wait(10):
                raise AssertionError("release timeout")

    def issue():
        invoice_thread.append(threading.get_ident())
        return _auto(engine, ids)

    def mutate(ready):
        with Session(engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
            db.get(VisitService, ids["line"]).price = Decimal("8.00")
            db.commit()

    event.listen(engine, "after_cursor_execute", pause_after_lines)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            issuer = pool.submit(issue)
            assert locked.wait(5)
            ready = threading.Event()
            writer = pool.submit(mutate, ready)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            status, invoice_id = issuer.result(timeout=12)
            writer.result(timeout=12)
        assert status == 200
        with Session(engine) as db:
            assert db.query(InvoiceItem).filter_by(invoice_id=invoice_id).one().unit_price == 10.0
            assert db.get(VisitService, ids["line"]).price == Decimal("8.00")
        # The subsequent change needs the still-unimplemented shared re-quote;
        # this test proves snapshot fencing only, not future invoice freshness.
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_lines)


@pytest.mark.parametrize("resource", ["patient", "service", "settings"])
def test_conflicting_reference_lock_fails_fast_and_is_retryable(auto_case, resource):
    engine, ids = auto_case
    with Session(engine) as setup:
        patient_id = setup.get(Visit, ids["visit"]).patient_id
        settings = BillingSettings()
        setup.add(settings)
        setup.flush()
        settings_id = settings.id
        setup.commit()
    with Session(engine) as editor:
        model, identity = {
            "patient": (Patient, patient_id),
            "service": (Service, ids["service"]),
            "settings": (BillingSettings, settings_id),
        }[resource]
        editor.query(model).filter(model.id == identity).with_for_update().one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            issuer = pool.submit(_auto, engine, ids)
            assert issuer.result(timeout=8)[0] == 409
        editor.rollback()
    status, invoice_id = _auto(engine, ids)
    assert status == 200 and invoice_id is not None


def test_first_settings_creation_does_not_release_visit_or_line_locks(auto_case):
    engine, ids = auto_case
    settings_inserted, release, pids = threading.Event(), threading.Event(), []
    invoice_thread = []

    def pause_after_settings(_conn, _cursor, statement, _params, _context, _many):
        if (threading.get_ident() in invoice_thread and "insert into billing_settings" in statement.lower()
            and not settings_inserted.is_set()):
            settings_inserted.set()
            if not release.wait(10):
                raise AssertionError("release timeout")

    def issue():
        invoice_thread.append(threading.get_ident())
        return _auto(engine, ids)

    def mutate(ready):
        with Session(engine) as db:
            pids.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
            ready.set()
            db.get(VisitService, ids["line"]).price = Decimal("6.00")
            db.commit()

    event.listen(engine, "after_cursor_execute", pause_after_settings)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            issuer = pool.submit(issue)
            assert settings_inserted.wait(5)
            ready = threading.Event()
            writer = pool.submit(mutate, ready)
            try:
                assert ready.wait(5)
                assert _is_blocked(engine, pids[0])
            finally:
                release.set()
            assert issuer.result(timeout=12)[0] == 200
            writer.result(timeout=12)
    finally:
        release.set()
        event.remove(engine, "after_cursor_execute", pause_after_settings)

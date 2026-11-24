"""Registrar invoice checkout and receipt regressions on disposable PostgreSQL."""

from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from threading import Barrier
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from tests.integration.test_registrar_benefit_decision_pg import (
    OWNER,
    RUNTIME,
    configured_benefit_db,  # noqa: F401
)

from app.api.v1.endpoints.registrar_wizard import _invoice
from app.core.config import settings
from app.models.clinic import Doctor
from app.models.encounter import Encounter
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.models.patient import Patient
from app.models.payment import Payment
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.all_free_approval import ALL_FREE_DECISION_REQUIRED
from app.services.payment_providers.base import PaymentResult

pytestmark = pytest.mark.integration
AMOUNT = Decimal("125.45")


@pytest.fixture(scope="module")
def checkout_database(configured_benefit_db):  # noqa: F811
    admin, runtime = configured_benefit_db
    with admin.begin() as conn:
        # The financial provisioners already grant the capability reads. These
        # permissions represent the existing app's receipt writer on this fixture.
        conn.exec_driver_sql(f"GRANT SELECT, INSERT ON payments TO {RUNTIME}")
        conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE payments_id_seq TO {RUNTIME}")
        conn.exec_driver_sql(
            f"GRANT UPDATE (provider_payment_id, provider_transaction_id, provider_data, updated_at) ON payments TO {RUNTIME}"
        )
        conn.exec_driver_sql(f"GRANT UPDATE (status, paid_at, provider_transaction_id) ON payment_invoices TO {RUNTIME}")
        conn.exec_driver_sql(f"GRANT UPDATE (id) ON visits TO {RUNTIME}")
        # Match the ticket projection's column reads without granting queue writes.
        ticket_columns = {
            "queue_entries": "id, queue_id, visit_id, patient_id, number, status",
            "daily_queues": "id, day, active, queue_tag, cabinet_number, queue_resource_id, specialist_id",
            "queue_resources": "id, display_name",
            "doctors": "id, user_id, cabinet",
        }
        for table, columns in ticket_columns.items():
            conn.exec_driver_sql(f"GRANT SELECT ({columns}) ON {table} TO {RUNTIME}")
            if conn.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass(:table)"),
                {"table": table},
            ).scalar_one():
                conn.exec_driver_sql(
                    f"CREATE POLICY synthetic_checkout_ticket_read ON {table} "
                    f"FOR SELECT TO {RUNTIME} USING (true)"
                )
        for table, policy, command, condition in (
            ("payments", "synthetic_checkout_insert", "INSERT", "WITH CHECK (true)"),
            ("visits", "synthetic_checkout_row_lock", "UPDATE", "USING (true) WITH CHECK (false)"),
        ):
            if conn.execute(
                text("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass(:table)"),
                {"table": table},
            ).scalar_one():
                conn.exec_driver_sql(f"CREATE POLICY {policy} ON {table} FOR {command} TO {RUNTIME} {condition}")
    return admin, runtime


@pytest.fixture
def invoice_engines(checkout_database, monkeypatch):
    for name, value in {
        "TRUSTED_DB_SCHEMA": "public",
        "TRUSTED_DB_SCHEMA_OWNER": OWNER,
        "TRUSTED_DB_RUNTIME_ROLE": RUNTIME,
        "TRUSTED_DB_OWNER_MEMBERS": (),
    }.items():
        monkeypatch.setattr(settings, name, value)
    return checkout_database


def _seed_invoice(admin, *, processing: bool):
    suffix = uuid4().hex[:12]
    with Session(admin) as db:
        patient = Patient(first_name="SYNTHETIC", last_name=f"INVOICE-{suffix}")
        service = Service(code=f"S-IV-{suffix}", name="Synthetic invoice item", price=AMOUNT, currency="UZS")
        db.add_all([patient, service])
        db.flush()
        encounter = Encounter(patient_id=patient.id, provenance="new")
        invoice = PaymentInvoice(
            patient_id=patient.id,
            total_amount=AMOUNT,
            currency="UZS",
            status="processing" if processing else "pending",
            provider="click" if processing else None,
            payment_method="click",
        )
        db.add_all([encounter, invoice])
        db.flush()
        if processing:
            invoice.provider_payment_id = f"invoice_{invoice.id}"
        visit_ids = []
        for amount in (AMOUNT, Decimal("0.00")):
            visit = Visit(
                patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2030, 1, 1),
                status="pending_confirmation", confirmation_context_epoch=1,
                discount_mode="all_free" if processing or amount == 0 else "none",
                approval_status="pending" if processing or amount == 0 else "approved",
            )
            db.add(visit)
            db.flush()
            db.add(VisitService(
                visit_id=visit.id, service_id=service.id, name="Synthetic invoice item",
                qty=1, price=amount, currency="UZS",
            ))
            db.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=amount))
            visit_ids.append(visit.id)
        result = (invoice.id, invoice.provider_payment_id, visit_ids)
        db.commit()
        return result


def _registrar():
    return SimpleNamespace(id=71, role="Registrar")


def test_pending_zero_visit_blocks_new_checkout_on_postgres(invoice_engines, monkeypatch):
    admin, runtime = invoice_engines
    invoice_id, _, _ = _seed_invoice(admin, processing=False)
    factory = Mock()
    monkeypatch.setattr(_invoice, "get_payment_manager", factory)

    with Session(runtime, autoflush=False) as db, pytest.raises(HTTPException) as denied:
        _invoice.init_invoice_payment(_invoice.InvoicePaymentRequest(invoice_id=invoice_id), db, _registrar())

    assert denied.value.status_code == 409
    assert denied.value.detail == ALL_FREE_DECISION_REQUIRED
    factory.assert_not_called()


def test_two_pollers_write_one_receipt_under_postgres_locks(invoice_engines, monkeypatch):
    admin, runtime = invoice_engines
    invoice_id, order, visit_ids = _seed_invoice(admin, processing=True)
    assert order
    reference = str(100_000 + invoice_id)
    synchronized = Barrier(2, timeout=10)
    manager = Mock()
    manager.supports_registrar_invoice_payment.return_value = True

    def check(provider, payment_id):
        assert (provider, payment_id) == ("click", order)
        synchronized.wait()
        return PaymentResult(
            success=True, payment_id=order, status="completed",
            provider_data={
                "merchant_trans_id": order, "status": 2, "amount": str(AMOUNT),
                "currency": "UZS", "click_trans_id": reference,
            },
        )

    manager.check_payment_status.side_effect = check
    monkeypatch.setattr(_invoice, "get_payment_manager", lambda: manager)

    def poll():
        with Session(runtime, autoflush=False) as db:
            try:
                return _invoice.check_invoice_status(invoice_id, db, _registrar())["status"]
            except HTTPException as error:
                assert error.status_code == 409
                assert error.detail == "Обращение занято, повторите оплату"
                return "busy"

    with ThreadPoolExecutor(max_workers=2) as pool:
        requests = [pool.submit(poll) for _ in range(2)]
        outcomes = [request.result(timeout=15) for request in requests]
    assert "paid" in outcomes
    assert set(outcomes) <= {"paid", "busy"}
    assert poll() == "paid"
    assert manager.check_payment_status.call_count == 2

    with Session(admin) as db:
        receipt = db.query(Payment).filter_by(provider_payment_id=order).one()
        assert (receipt.visit_id, receipt.amount, receipt.currency, receipt.provider_transaction_id) == (
            visit_ids[0], AMOUNT, "UZS", reference,
        )
        assert db.get(PaymentInvoice, invoice_id).status == "paid"
        assert [db.get(Visit, visit_id).status for visit_id in visit_ids] == [
            "pending_confirmation", "pending_confirmation",
        ]


def test_paid_invoice_reads_existing_ticket_in_read_only_postgres_transaction(
    invoice_engines, monkeypatch,
):
    admin, runtime = invoice_engines
    invoice_id, _, visit_ids = _seed_invoice(admin, processing=False)
    with Session(admin) as db:
        invoice = db.get(PaymentInvoice, invoice_id)
        invoice.status = "paid"
        visit = db.get(Visit, visit_ids[0])
        visit.status = "confirmed"
        physician_user = User(
            username=f"synthetic-ticket-{uuid4().hex}",
            role="Doctor", full_name="Synthetic Doctor", hashed_password="!",
        )
        db.add(physician_user)
        db.flush()
        doctor = Doctor(user_id=physician_user.id, specialty="cardiology", active=True)
        db.add(doctor)
        db.flush()
        queue = DailyQueue(
            day=visit.visit_date, specialist_id=doctor.id, active=True,
            queue_tag="cardiology_common", cabinet_number="71",
        )
        db.add(queue)
        db.flush()
        db.add(OnlineQueueEntry(
            queue_id=queue.id, visit_id=visit.id, patient_id=visit.patient_id,
            number=41, status="waiting",
        ))
        queue_id = queue.id
        db.commit()

    manager = Mock(side_effect=AssertionError("stored paid status must not call provider"))
    monkeypatch.setattr(_invoice, "get_payment_manager", manager)
    with Session(runtime, autoflush=False) as db:
        db.execute(text("SET TRANSACTION READ ONLY"))
        assert db.execute(text("SHOW transaction_read_only")).scalar_one() == "on"
        assert db.execute(
            text("SELECT has_table_privilege(current_user, 'queue_entries', 'INSERT,UPDATE,DELETE')")
        ).scalar_one() is False
        first = _invoice.check_invoice_status(invoice_id, db, _registrar())
        second = _invoice.check_invoice_status(invoice_id, db, _registrar())
        assert first == second
        assert first["status"] == "paid"
        ticket, = first["print_tickets"]
        assert (ticket["queue_id"], ticket["queue_number"], ticket["doctor_cabinet"]) == (
            queue_id, 41, "71",
        )
        assert ticket["doctor_name"] == "Synthetic Doctor"
    manager.assert_not_called()

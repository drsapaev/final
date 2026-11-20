"""Verify legacy invoice settlement with independent restricted PostgreSQL sessions."""

from __future__ import annotations

import os
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session

from app.api.v1.endpoints.billing import PaymentCreate, record_payment
from app.db.capability_namespace import capability_schema_name
from app.models.billing import BillingSettings, Invoice, InvoiceStatus
from app.models.payment import Payment, PaymentClientRequest
from app.models.user import User
from app.services import payment_client_requests
from app.services.billing_api_service import BillingApiDomainError, BillingApiService
from app.services.billing_service import BillingService
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_refund_cross_channel_budget import (
    _install_cashier_receipt_policy,
)
from tests.integration.test_staff_confirmation_guard_pg import (
    _module,
    isolated_staff_guard_postgres,
)

pytestmark = pytest.mark.integration


@pytest.fixture
def legacy_invoice_pg(monkeypatch):
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    ci_service = (
        os.getenv("CI", "").lower() == "true"
        and url.database == "clinicdb"
        and url.host in {"localhost", "127.0.0.1", "::1"}
    )
    if url.get_backend_name() != "postgresql" or not (
        ci_service or (url.database or "").startswith("clinic_test")
    ):
        pytest.skip("requires a disposable PostgreSQL database")

    with isolated_staff_guard_postgres(url, monkeypatch) as (owner, runtime, ids):
        with owner.begin() as conn:
            quote = conn.dialect.identifier_preparer.quote
            schema_name, runtime_name = conn.dialect.default_schema_name, runtime.url.username
            schema, role = quote(schema_name), quote(runtime_name)
            private = quote(capability_schema_name(schema_name))
            migration = _migration("0123_reconciliation_fence.py")
            migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema_name}))
            migration.upgrade()
            conn.exec_driver_sql(f"ALTER TABLE {schema}.click_callback_receipts ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"ALTER TABLE {schema}.click_callback_receipts FORCE ROW LEVEL SECURITY")
            schema_owner = conn.scalar(text("SELECT CURRENT_USER"))
            capability = conn.scalar(text("""
                SELECT pg_catalog.pg_get_userbyid(p.proowner) FROM pg_catalog.pg_proc p
                WHERE p.oid=pg_catalog.to_regprocedure(:signature)
            """), {"signature": f"{private}.financial_lock_rows(text,integer[])"})
            conn.exec_driver_sql(f"GRANT SELECT ON {schema}.billing_settings, {schema}.clinic_settings TO {role}")
            conn.exec_driver_sql(
                f"GRANT SELECT, UPDATE (paid_amount, balance, status, paid_date, updated_at) "
                f"ON {schema}.invoices TO {role}"
            )
            conn.exec_driver_sql(
                f"CREATE POLICY legacy_billing_read ON {schema}.invoices FOR SELECT TO {role} USING (true)"
            )
            conn.exec_driver_sql(
                f"CREATE POLICY legacy_billing_write ON {schema}.invoices FOR UPDATE TO {role} "
                "USING (true) WITH CHECK (true)"
            )
            conn.exec_driver_sql(
                f"GRANT INSERT, UPDATE (receipt_no, provider_payment_id, updated_at) "
                f"ON {schema}.payments TO {role}"
            )
            conn.exec_driver_sql(
                f"CREATE POLICY legacy_billing_receipt ON {schema}.payments FOR INSERT TO {role} WITH CHECK (true)"
            )
            conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {schema}.payments_id_seq TO {role}")
            _install_cashier_receipt_policy(conn, schema_name, runtime_name)
            receipt_guard = _migration("0138_billing_payment_receipts.py")
            receipt_guard.op = Operations(
                MigrationContext.configure(conn, opts={"version_table_schema": schema_name})
            )
            receipt_guard.upgrade()

        root = Path(__file__).resolve().parents[3]
        provisioner = _module(root / "scripts/provision_reconciliation_fence_role.py")
        provisioner.provision(
            owner, schema=schema_name, expected_owner=schema_owner,
            backend_role=runtime_name, capability_role=capability,
        )

        with Session(owner, expire_on_commit=False) as db:
            cashier = User(
                username=f"synthetic-billing-{uuid4().hex[:12]}", hashed_password="!",
                role="Cashier", is_active=True,
            )
            invoice = Invoice(
                invoice_number=f"SYNTHETIC-{uuid4().hex[:12]}",
                patient_id=ids["patient"],
                visit_id=ids["visit"],
                subtotal=10,
                total_amount=10,
                paid_amount=0,
                balance=10,
            )
            db.add_all([invoice, cashier, BillingSettings(currency_code="UZS")])
            db.commit()
            invoice_id = invoice.id
            ids["cashier"] = cashier.id
        yield owner, runtime, invoice_id, ids


def _record(db: Session, *, invoice_id: int, actor_id: int, amount: int | Decimal) -> int:
    payment = BillingService(db).record_payment(
        invoice_id=invoice_id,
        amount=amount,
        payment_method="cash",
        current_user=SimpleNamespace(id=actor_id),
        commit=False,
    )
    return payment.id


def _assert_settled(owner, invoice_id, visit_id, expected_amounts):
    with Session(owner) as db:
        payments = db.query(Payment).filter_by(visit_id=visit_id).order_by(Payment.id).all()
        assert [payment.amount for payment in payments] == expected_amounts
        assert all(payment.status == "paid" and payment.paid_at for payment in payments)
        assert len({payment.receipt_no for payment in payments}) == len(payments)
        invoice = db.get(Invoice, invoice_id)
        assert invoice.paid_amount == sum(expected_amounts)
        assert invoice.balance == 0
        assert invoice.status == InvoiceStatus.PAID
        assert invoice.paid_date is not None


def test_concurrent_record_payment_same_invoice_serialized(legacy_invoice_pg):
    owner, runtime, invoice_id, ids = legacy_invoice_pg
    with Session(runtime) as first, Session(runtime) as second:
        _record(first, invoice_id=invoice_id, actor_id=ids["stage"], amount=10)
        with pytest.raises(HTTPException, match="Обращение занято") as busy:
            _record(second, invoice_id=invoice_id, actor_id=ids["cashier"], amount=6)
        assert busy.value.status_code == 409
        first.commit()
        with pytest.raises(HTTPException) as settled:
            _record(second, invoice_id=invoice_id, actor_id=ids["cashier"], amount=6)
        assert settled.value.status_code == 400
    _assert_settled(owner, invoice_id, ids["visit"], [Decimal("10.00")])


def test_concurrent_partial_payment_reloads_the_invoice_balance(legacy_invoice_pg):
    owner, runtime, invoice_id, ids = legacy_invoice_pg
    with Session(runtime) as first, Session(runtime, expire_on_commit=False) as second:
        cached_invoice = second.get(Invoice, invoice_id)
        assert cached_invoice.paid_amount == 0
        first_receipt = _record(first, invoice_id=invoice_id, actor_id=ids["stage"], amount=Decimal("4.13"))
        first.commit()
        assert cached_invoice.paid_amount == 0
        second_receipt = _record(second, invoice_id=invoice_id, actor_id=ids["cashier"], amount=Decimal("5.87"))
        assert second_receipt != first_receipt
        second.commit()
    _assert_settled(owner, invoice_id, ids["visit"], [Decimal("4.13"), Decimal("5.87")])


def test_record_payment_persists_across_sessions(legacy_invoice_pg):
    owner, runtime, invoice_id, ids = legacy_invoice_pg
    with Session(runtime) as db:
        assert not db.execute(
            text("SELECT pg_catalog.has_table_privilege(CURRENT_USER,'payments','SELECT')")
        ).scalar_one()
        _record(db, invoice_id=invoice_id, actor_id=ids["stage"], amount=10)
        db.commit()
    _assert_settled(owner, invoice_id, ids["visit"], [Decimal("10.00")])


def test_invoice_edit_cannot_overwrite_a_concurrently_settled_status(legacy_invoice_pg):
    owner, runtime, invoice_id, ids = legacy_invoice_pg
    with Session(owner, expire_on_commit=False) as editor, Session(runtime) as cashier:
        cached = editor.get(Invoice, invoice_id)
        assert cached.status == InvoiceStatus.DRAFT
        _record(cashier, invoice_id=invoice_id, actor_id=ids["cashier"], amount=4)
        cashier.commit()
        assert cached.status == InvoiceStatus.DRAFT
        service = BillingApiService(editor)
        with pytest.raises(BillingApiDomainError) as rejected:
            service.update_invoice(invoice_id=invoice_id, update_data={"status": InvoiceStatus.CANCELLED})
        assert rejected.value.status_code == 409
        assert cached.status == InvoiceStatus.PARTIALLY_PAID
        editor.rollback()
        with pytest.raises(BillingApiDomainError) as delete:
            service.delete_invoice(invoice_id=invoice_id)
        assert delete.value.status_code == 400
    with Session(owner) as db:
        invoice = db.get(Invoice, invoice_id)
        assert invoice.status == InvoiceStatus.PARTIALLY_PAID and invoice.paid_amount == 4
        assert db.query(Payment).filter_by(visit_id=ids["visit"]).count() == 1


def test_postgres_billing_report_uses_the_full_period_for_totals_and_statuses(legacy_invoice_pg):
    owner, _, invoice_id, ids = legacy_invoice_pg
    report_day = date(2031, 3, 4)
    midday = datetime(2031, 3, 4, 12, 30)
    next_day = midday + timedelta(days=1)
    with Session(owner) as db:
        assert db.get_bind().dialect.name == "postgresql"
        invoice = db.get(Invoice, invoice_id)
        invoice.issue_date = midday
        invoice.status = InvoiceStatus.PENDING
        db.add_all([
            Invoice(
                invoice_number=f"SYNTHETIC-{uuid4().hex[:12]}",
                patient_id=ids["patient"], total_amount=5, balance=5,
                issue_date=next_day, status=InvoiceStatus.OVERDUE,
            ),
            Payment(visit_id=ids["visit"], amount=Decimal("4.25"), created_at=midday.replace(tzinfo=UTC)),
            Payment(visit_id=ids["visit"], amount=Decimal("5.75"), created_at=next_day.replace(tzinfo=UTC)),
        ])
        db.commit()
        db.execute(text("SET LOCAL TIME ZONE 'UTC'"))
        report = BillingApiService(db).get_billing_analytics(date_from=report_day, date_to=report_day)

    assert report["summary"]["total_invoices"] == 1
    assert report["summary"]["total_payments"] == 1
    assert report["summary"]["payments_amount"] == Decimal("4.25")
    assert [item["status"] for item in report["status_breakdown"]] == [InvoiceStatus.PENDING]


@pytest.mark.parametrize("amount", [Decimal("4.00"), Decimal("10.00")], ids=["partial", "fully-settled"])
def test_duplicate_billing_operation_replays_after_a_missed_lookup(legacy_invoice_pg, monkeypatch, amount):
    owner, runtime, invoice_id, ids = legacy_invoice_pg
    actor = SimpleNamespace(id=ids["cashier"])
    form = PaymentCreate(invoice_id=invoice_id, amount=amount, payment_method="cash", client_request_id=uuid4())
    key = str(form.client_request_id)
    with Session(runtime) as db:
        first = record_payment(form, db=db, current_user=actor, exact_amount=amount)

    lookup = payment_client_requests.find_payment_client_request
    reads = 0

    def miss_precheck(session, request_id):
        nonlocal reads
        reads += 1
        return None if reads == 1 else lookup(session, request_id)

    monkeypatch.setattr(payment_client_requests, "find_payment_client_request", miss_precheck)
    with Session(runtime) as db:
        replay = record_payment(form, db=db, current_user=actor, exact_amount=amount)
        assert replay == first
        assert not db.scalar(text(
            "SELECT has_table_privilege(CURRENT_USER,'payment_client_requests','UPDATE,DELETE')"
        ))
    assert reads == 2

    with Session(owner) as db:
        receipt = db.query(Payment).filter_by(visit_id=ids["visit"]).one()
        anchor = db.query(PaymentClientRequest).filter_by(client_request_id=key).one()
        assert receipt.id == first.id and receipt.client_request_id == key
        assert anchor.response_payload["recorded_by"] == actor.id
        invoice = db.get(Invoice, invoice_id)
        assert invoice.paid_amount == float(amount) and invoice.balance == float(Decimal(10) - amount)

        with pytest.raises(DBAPIError, match="immutable billing payment receipt"), db.begin_nested():
            db.execute(text("UPDATE payment_client_requests SET request_fingerprint=NULL WHERE client_request_id=:key"),
                       {"key": key})
        with pytest.raises(DBAPIError, match="immutable billing payment receipt"), db.begin_nested():
            db.execute(text("DELETE FROM payment_client_requests WHERE client_request_id=:key"), {"key": key})
        db.execute(text("DELETE FROM users WHERE id=:actor"), {"actor": actor.id})
        db.commit()
        assert anchor.created_by is None and anchor.response_payload["recorded_by"] == actor.id

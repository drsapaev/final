"""Real PostgreSQL nonowner coverage of transaction/savepoint preflight."""

import importlib.util
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.db.capability_namespace import capability_schema_name
from app.models.click_callback_receipt import (
    ClickCallbackReceipt,
    ClickReceiptKeyVersion,
)
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.provider_attempt import (
    ProviderActiveVisitReservation,
    ProviderAttempt,
    ProviderAttemptVisit,
)
from app.models.service import Service
from app.models.visit import Visit, VisitService
from app.services.encounter_financial_fence import (
    FinancialFenceError,
    _financial_schema,
    _lock_full_financial_closure,
    acquire_reconciliation_mutex,
    lock_financial_group,
    preflight_payment_groups,
    requote_draft_invoices,
)
from app.services.payment_invariant_service import PaymentInvariantService
from tests.integration.test_encounter_financial_role_pg import _provision_module
from tests.integration.test_encounter_migration_pg import _migration


@pytest.fixture
def pg_case(monkeypatch):
    from app.core.config import settings

    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    suffix = uuid.uuid4().hex
    schema, backend, capability, recon_cap = "batch_" + suffix, "batchback_" + suffix, "batchcap_" + suffix, "batchrecon_" + suffix
    password = "synthetic" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        owner = conn.execute(text("SELECT CURRENT_USER")).scalar_one()
        bootstrap = _migration("0112_doctor_price_context.py")
        bootstrap.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
        bootstrap._bootstrap_capability_namespace(schema)
        conn.execute(text(f'CREATE ROLE "{backend}" LOGIN PASSWORD \'{password}\''))
        conn.execute(text(f'CREATE ROLE "{capability}" NOLOGIN'))
        conn.execute(text(f'CREATE ROLE "{recon_cap}" NOLOGIN'))
    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA", schema)
    monkeypatch.setattr(settings, "TRUSTED_DB_SCHEMA_OWNER", owner)
    monkeypatch.setattr(settings, "TRUSTED_DB_RUNTIME_ROLE", backend)
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    runtime = None
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            patient = Patient(first_name="SYNTHETIC", last_name="Batch")
            service = Service(code="SYNTHETIC-BATCH", name="SYNTHETIC", price=Decimal("1.00"), active=True)
            db.add_all([patient, service])
            db.flush()
            encounters = [Encounter(patient_id=patient.id, provenance="new") for _ in range(2)]
            db.add_all(encounters)
            db.flush()
            visits = [Visit(patient_id=patient.id, encounter_id=encounters[i % 2].id,
                            confirmation_context_epoch=1, status="pending_confirmation", visit_date=date(2099,1,1))
                      for i in range(4)]
            db.add_all(visits)
            db.flush()
            db.add_all([VisitService(visit_id=v.id, service_id=service.id, name="SYNTHETIC", qty=1,
                                     price=Decimal("1.00"), currency="UZS") for v in visits])
            db.flush()
            ids = [v.id for v in visits]
            db.commit()
        provision = _provision_module()
        with engine.begin() as conn:
            migration = _migration("0118_encounter_financial_fence.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            recon_migration = _migration("0123_reconciliation_fence.py")
            recon_migration.op = Operations(MigrationContext.configure(conn))
            recon_migration.upgrade()
            for table in provision.TABLES:
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY'))
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".click_callback_receipts ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'ALTER TABLE "{schema}".click_callback_receipts FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{backend}"'))
            conn.execute(text(f'GRANT SELECT ON "{schema}".all_free_requests TO "{backend}"'))
            conn.execute(text(f'CREATE POLICY allfree_backend_select ON "{schema}".all_free_requests FOR SELECT TO "{backend}" USING (true)'))
        provision.provision(engine, schema=schema, backend_role=backend, capability_role=capability, expected_owner=owner)
        path = Path(__file__).resolve().parents[3] / "scripts/provision_reconciliation_fence_role.py"
        spec = importlib.util.spec_from_file_location("reconciliation_provision", path)
        recon_provision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recon_provision)
        recon_provision.provision(engine, schema=schema, backend_role=backend, capability_role=recon_cap, expected_owner=owner)
        runtime = create_engine(url.set(username=backend, password=password), pool_size=1, max_overflow=1,
                                connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
        yield runtime, ids, engine
    finally:
        if runtime:
            runtime.dispose()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(capability_schema_name(schema), cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(text(f'DROP OWNED BY "{backend}"'))
            conn.execute(text(f'DROP OWNED BY "{capability}"'))
            conn.execute(text(f'DROP OWNED BY "{recon_cap}"'))
            conn.execute(text(f'DROP ROLE "{backend}"'))
            conn.execute(text(f'DROP ROLE "{capability}"'))
            conn.execute(text(f'DROP ROLE "{recon_cap}"'))
        admin.dispose()


@pytest.mark.parametrize("finish", ["commit", "rollback"])
@pytest.mark.parametrize("kind", ["session", "connection"])
def test_savepoint_release_or_rollback_invalidates_marker(pg_case, finish, kind):
    runtime, ids, _ = pg_case
    with Session(runtime) as db:
        db.connection()
        savepoint = db.begin_nested() if kind == "session" else db.connection().begin_nested()
        preflight_payment_groups(db, ids[:2])
        getattr(savepoint, finish)()
        with pytest.raises(FinancialFenceError, match="Транзакция"):
            preflight_payment_groups(db, [ids[0]])
        db.rollback()
    with runtime.connect() as conn:
        assert conn.execute(text("SHOW lock_timeout")).scalar_one() == "5s"


def test_new_savepoint_and_reused_root_cannot_inherit_old_marker(pg_case):
    runtime, ids, _ = pg_case
    with Session(runtime) as db:
        nested = db.begin_nested()
        preflight_payment_groups(db, [ids[0]])
        nested.rollback()
        replacement = db.begin_nested()
        with pytest.raises(FinancialFenceError, match="Транзакция"):
            preflight_payment_groups(db, [ids[0]])
        replacement.rollback()
        db.rollback()
        # A different root transaction must perform its own full preflight.
        preflight_payment_groups(db, ids[:2])
        db.rollback()


def test_competing_group_preflight_rolls_back_before_409(pg_case):
    runtime, ids, _ = pg_case
    with Session(runtime) as holder:
        preflight_payment_groups(holder, [ids[0]])
        def competitor():
            with Session(runtime) as db:
                with pytest.raises(HTTPException) as error:
                    PaymentInvariantService(db).preflight_payment_groups([ids[2]])
                assert error.value.status_code == 409
                assert not db.in_transaction()
                return db.execute(text("SHOW lock_timeout")).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(competitor).result(timeout=10) == "5s"
        holder.rollback()


def _reservation_history(engine, visit_id):
    with Session(engine) as db:
        visit = db.get(Visit, visit_id)
        attempt = ProviderAttempt(public_id=str(uuid.uuid4()), target_kind="payment_invoice", invoice_id_snapshot=123,
                                  actor_user_id_snapshot=1, provider="click", merchant_hash="a" * 64,
                                  order_ref=str(uuid.uuid4()), fingerprint="b" * 64, amount_minor="100",
                                  currency="UZS", currency_exponent=2, status="prepared")
        db.add(attempt)
        db.flush()
        history = ProviderAttemptVisit(attempt_id=attempt.id, visit_id=visit_id, visit_id_snapshot=visit_id,
                                       patient_id_snapshot=visit.patient_id, context_epoch=1, amount_minor="100")
        db.add(history)
        db.flush()
        result = (attempt.id, history.id)
        db.commit()
        return result


def test_active_reservation_serializes_with_payment_preflight_both_orders(pg_case):
    runtime, ids, admin_engine = pg_case
    attempt_id, history_id = _reservation_history(admin_engine, ids[0])
    with Session(admin_engine) as reservation:
        reservation.add(ProviderActiveVisitReservation(visit_id=ids[0], attempt_id=attempt_id,
                                                        attempt_visit_id=history_id))
        reservation.flush()  # FK holds KEY SHARE before the competing Visit lock.
        def competing_payment():
            with Session(runtime) as db:
                with pytest.raises(HTTPException) as error:
                    PaymentInvariantService(db).preflight_payment_groups([ids[0]])
                assert error.value.status_code == 409
                assert not db.in_transaction()
                return db.execute(text("SHOW lock_timeout")).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(competing_payment).result(timeout=10) == "5s"
        reservation.commit()
    with Session(runtime) as db:
        PaymentInvariantService(db).preflight_payment_groups([ids[0]])
        assert PaymentInvariantService(db)._has_unresolved_payment_intent(ids[0])
        with pytest.raises(HTTPException) as blocked:
            PaymentInvariantService(db).assert_no_unresolved_payment_intent(ids[2])
        assert blocked.value.status_code == 409
        db.rollback()
    with Session(admin_engine) as db:
        db.query(ProviderActiveVisitReservation).filter_by(visit_id=ids[0]).delete()
        db.commit()
    with Session(runtime) as holder:
        PaymentInvariantService(holder).preflight_payment_groups([ids[0]])
        PaymentInvariantService(holder).assert_no_unresolved_payment_intent(ids[0])
        def competing_reservation():
            from sqlalchemy.exc import DBAPIError
            with Session(admin_engine) as db:
                db.execute(text("SET LOCAL lock_timeout='100ms'"))
                db.add(ProviderActiveVisitReservation(visit_id=ids[0], attempt_id=attempt_id,
                                                       attempt_visit_id=history_id))
                try:
                    db.flush()
                except DBAPIError as exc:
                    db.rollback()
                    return getattr(exc.orig, "sqlstate", None)
                return "unexpected-success"
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(competing_reservation).result(timeout=10) == "55P03"
        holder.rollback()
    with runtime.connect() as conn:
        assert conn.execute(text("SHOW lock_timeout")).scalar_one() == "5s"


def test_hidden_reservations_cannot_be_treated_as_absent(pg_case):
    runtime, ids, admin_engine = pg_case
    with admin_engine.begin() as conn:
        schema = conn.dialect.default_schema_name
        conn.execute(text(f'ALTER POLICY financial_backend_select ON "{schema}".provider_active_visit_reservations USING (false)'))
    with Session(runtime) as db:
        with pytest.raises(FinancialFenceError):
            preflight_payment_groups(db, [ids[0]])
        db.rollback()


def test_hourly_report_nonowner_force_rls_rejects_hidden_payments(pg_case):
    import asyncio
    from datetime import datetime

    from app.api.v1.endpoints.cashier._stats import get_hourly_stats_by_currency
    from app.models.payment import Payment

    runtime, ids, admin_engine = pg_case
    with Session(admin_engine) as db:
        db.add(Payment(visit_id=ids[0], amount=Decimal("10.25"), currency="USD", method="cash",
                       status="paid", created_at=datetime(2099, 1, 1, 10, 30)))
        db.commit()
    with admin_engine.begin() as conn:
        schema = conn.dialect.default_schema_name
    with Session(runtime) as db:
        db.connection()  # The pre-auth schema pin initializes the dialect first.
        data = asyncio.run(get_hourly_stats_by_currency(db=db, current_user=None, target_date=date(2099, 1, 1)))
        assert data == [{"hour": 10, "currency": "USD", "count": 1, "amount": "10.25",
                         "requires_reconciliation": False}]
        db.rollback()
    with admin_engine.begin() as conn:
        conn.execute(text(f'ALTER POLICY financial_backend_select ON "{schema}".payments USING (false)'))
    with Session(runtime) as db:
        db.connection()
        with pytest.raises(HTTPException) as error:
            asyncio.run(get_hourly_stats_by_currency(db=db, current_user=None, target_date=date(2099, 1, 1)))
        assert error.value.status_code == 503
        db.rollback()


def test_zero_link_transitive_closure_and_concurrent_insert(pg_case):
    runtime, ids, admin_engine = pg_case
    with Session(admin_engine) as db:
        first = db.get(Visit, ids[0])
        invoice = PaymentInvoice(patient_id=first.patient_id, total_amount=Decimal("1.00"), status="pending", currency="UZS")
        db.add(invoice)
        db.flush()
        invoice_id = invoice.id
        db.add(PaymentInvoiceVisit(invoice_id=invoice_id, visit_id=ids[0], visit_amount=Decimal("1.00")))
        db.commit()
    with Session(runtime) as holder:
        preflight_payment_groups(holder, [ids[0]])
        def insert_link():
            from sqlalchemy.exc import DBAPIError
            with Session(admin_engine) as db:
                db.execute(text("SET LOCAL lock_timeout='100ms'"))
                try:
                    db.add(PaymentInvoiceVisit(invoice_id=invoice_id, visit_id=ids[1], visit_amount=Decimal("0.00")))
                    db.flush()
                except DBAPIError as exc:
                    db.rollback()
                    return getattr(exc.orig, "sqlstate", None)
                return "unexpected-success"
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(insert_link).result(timeout=10) == "55P03"
        holder.rollback()
    with Session(admin_engine) as db:
        db.add(PaymentInvoiceVisit(invoice_id=invoice_id, visit_id=ids[1], visit_amount=Decimal("0.00")))
        db.commit()
    with Session(runtime) as db:
        preflight_payment_groups(db, [ids[0]])
        # The zero link pulls the second encounter and its sibling into the
        # same sorted preflight. No late expansion is attempted.
        preflight_payment_groups(db, [ids[3]])
        db.rollback()


def test_price_decision_locks_cross_encounter_invoice_before_requote(pg_case):
    from sqlalchemy.exc import DBAPIError
    runtime, ids, admin_engine = pg_case
    with Session(admin_engine) as db:
        first = db.get(Visit, ids[0])
        invoice = PaymentInvoice(patient_id=first.patient_id, total_amount=Decimal("2.00"), status="pending", currency="UZS")
        db.add(invoice)
        db.flush()
        invoice_id = invoice.id
        db.add_all([PaymentInvoiceVisit(invoice_id=invoice_id, visit_id=ids[0], visit_amount=Decimal("1.00")),
                    PaymentInvoiceVisit(invoice_id=invoice_id, visit_id=ids[1], visit_amount=Decimal("1.00"))])
        db.commit()
    with Session(admin_engine) as competing:
        competing.query(Visit.id).filter(Visit.id == ids[1]).with_for_update().one()
        with Session(runtime) as actor:
            with pytest.raises(DBAPIError) as error:
                lock_financial_group(actor, ids[0])
            assert getattr(error.value.orig, "sqlstate", None) == "55P03"
            actor.rollback()
        competing.rollback()
    with Session(runtime) as db:
        group = lock_financial_group(db, ids[0])
        requote_draft_invoices(group, {ids[0]: Decimal("0.50"), ids[2]: Decimal("1.00")})
        db.commit()
    with Session(admin_engine) as db:
        links = db.query(PaymentInvoiceVisit).filter_by(invoice_id=invoice_id).all()
        assert {link.visit_id: link.visit_amount for link in links} == {ids[0]: Decimal("0.50"), ids[1]: Decimal("1.00")}
        assert db.get(PaymentInvoice, invoice_id).total_amount == Decimal("1.50")


def test_internal_reconciliation_reads_pending_but_payment_still_denies(pg_case):
    runtime, ids, admin_engine = pg_case
    with Session(admin_engine) as db:
        db.add(ClickReceiptKeyVersion(version="synthetic", commitment="a" * 64))
        db.flush()
        db.add(ClickCallbackReceipt(event_key="b" * 64, body_digest="c" * 64, variant_slot=0,
            phase="complete", confidence="authenticated", media_type="application/json", body_size=1,
            key_version="synthetic", ciphertext=b"synthetic"))
        db.commit()
    with Session(runtime) as db:
        db.connection()  # The operator route already opened its pinned transaction.
        schema = _financial_schema(db)
        _lock_full_financial_closure(db, {ids[0]}, schema)
        with pytest.raises(FinancialFenceError):
            acquire_reconciliation_mutex(db, None)
        assert acquire_reconciliation_mutex(db, schema) is True
        db.rollback()
    with Session(runtime) as db:
        with pytest.raises(FinancialFenceError, match="сверки"):
            preflight_payment_groups(db, [ids[0]])
        db.rollback()

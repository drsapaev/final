"""Real PostgreSQL subject locks, All Free privileges and confirmation races.

The synthetic schema installs the actual reviewed capabilities for these tests.
"""
from __future__ import annotations

import importlib.util
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.base_class import Base
from app.db.capability_namespace import capability_schema_name
from app.models.all_free_request import AllFreeRequest
from app.models.authentication import TokenBlacklist
from app.models.encounter import Encounter
from app.models.patient import Patient
from app.models.payment_invoice import PaymentInvoice, PaymentInvoiceVisit
from app.models.service import Service
from app.models.user import User
from app.models.visit import Visit, VisitService
from app.services.all_free_guard import (
    AllFreeGuardError,
    PendingAllFreeError,
    lock_visit_without_pending,
)
from app.services.all_free_request_service import (
    AllFreeRequestError,
    AllFreeRequestService,
)
from app.services.profile_contact_security import ProfileBearerContext
from app.services.registrar_cart_replay import (
    RegistrarCartReceipt,
    registrar_cart_receipt_is_current,
)
from app.services.staff_confirmation_guard import lock_staff_confirmation_subjects
from app.services.visit_lifecycle_service import VisitLifecycleService


def _module(path: Path):
    spec = importlib.util.spec_from_file_location("synthetic_" + uuid4().hex, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def guarded_pg(monkeypatch):
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    with isolated_staff_guard_postgres(url, monkeypatch) as database:
        yield database


@contextmanager
def isolated_staff_guard_postgres(url, monkeypatch):
    """Set up migrated capabilities in a new schema of a disposable database."""
    suffix = uuid4().hex
    schema, runtime, subject_cap, financial_cap = ("staff_guard_" + suffix, "staff_runtime_" + suffix,
                                                     "staff_subject_" + suffix, "staff_finance_" + suffix)
    decision_cap = "staff_decision_" + suffix
    private = capability_schema_name(schema)
    password = secrets.token_urlsafe(24)
    root = Path(__file__).resolve().parents[3]
    admin = sa.create_engine(url, hide_parameters=True)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        owner = conn.execute(sa.text("SELECT CURRENT_USER")).scalar_one()
        for role, login in ((runtime, True), (subject_cap, False), (financial_cap, False), (decision_cap, False)):
            query = sa.text("SELECT pg_catalog.format('CREATE ROLE %I ' || CAST(:kind AS text) || ' NOSUPERUSER NOBYPASSRLS PASSWORD %L', CAST(:role AS text), CAST(:password AS text))")
            ddl = conn.execute(query, {"kind": "LOGIN" if login else "NOLOGIN", "role": role, "password": password}).scalar_one()
            conn.exec_driver_sql(ddl)
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"}, hide_parameters=True)
    runtime_engine = None
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(engine)
        with engine.begin() as conn:
            # Apply the actual migration rather than an ORM-only facsimile.
            conn.execute(sa.text("ALTER TABLE visits DROP COLUMN confirmation_context_epoch"))
            opts = {"version_table_schema": schema}
            for name in ("0102_visit_confirmation_context.py",):
                migration = _module(root / "backend/alembic/versions" / name)
                migration.op = Operations(MigrationContext.configure(conn, opts=opts))
                migration.upgrade()
            for table in ("all_free_request_events", "all_free_request_lines", "all_free_requests"):
                conn.execute(sa.text(f'DROP TABLE "{schema}"."{table}"'))
            conn.execute(sa.text("DROP INDEX uq_visits_allfree_identity"))
            conn.execute(sa.text("DROP INDEX uq_visit_services_allfree_identity"))
            conn.execute(sa.text("ALTER TABLE visits DROP COLUMN allfree_encounter_identity"))
            migration = _module(root / "backend/alembic/versions/0107_all_free_requests.py")
            migration.op = Operations(MigrationContext.configure(conn, opts=opts))
            migration.upgrade()
            bootstrap = _module(root / "backend/alembic/versions/0112_doctor_price_context.py")
            bootstrap.op = Operations(MigrationContext.configure(conn, opts=opts))
            bootstrap._bootstrap_capability_namespace(schema)
            for name in ("0114_all_free_visibility.py", "0115_confirmation_trigger_path.py",
                         "0116_patient_owner_confirmation.py", "0118_encounter_financial_fence.py",
                         "0120_all_free_decision_capability.py"):
                migration = _module(root / "backend/alembic/versions" / name)
                migration.op = Operations(MigrationContext.configure(conn, opts=opts))
                migration.upgrade()
            # Metadata already created the 0125 evidence table; install its
            # actual reviewed quote capability for this isolated partial graph.
            benefit_migration = _module(root / "backend/alembic/versions/0125_benefit_visibility.py")
            benefit_migration.op = Operations(MigrationContext.configure(conn, opts=opts))
            benefit_migration._create_quote_function(f'"{schema}"', f'"{private}"')
            for table in ("patients", "visits", "encounters", "visit_services", "payment_invoices", "payment_invoice_visits",
                          "payments", "payment_visits", "payment_webhooks", "payment_transactions", "invoices",
                          "provider_active_visit_reservations", "provider_attempt_visits", "provider_reconciliation_events",
                          "all_free_requests", "users", "token_blacklist", "encounter_benefit_applications",
                          "encounter_benefit_allocations", "encounter_benefit_events", "encounter_benefit_visit_snapshots"):
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY')
                conn.exec_driver_sql(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY')
            for table in ("users", "token_blacklist"):
                conn.exec_driver_sql(f'GRANT SELECT ON "{schema}"."{table}" TO "{runtime}"')
                conn.exec_driver_sql(f'CREATE POLICY staff_runtime_select ON "{schema}"."{table}" FOR SELECT TO "{runtime}" USING (true)')
            conn.exec_driver_sql(f'GRANT UPDATE (auth_epoch) ON "{schema}".users TO "{runtime}"')
            conn.exec_driver_sql(f'GRANT SELECT ON "{schema}".emr_records TO "{runtime}"')
            conn.exec_driver_sql(f'CREATE POLICY staff_user_lock ON "{schema}".users FOR UPDATE TO "{runtime}" USING (true) WITH CHECK (false)')
            conn.exec_driver_sql(f'GRANT UPDATE (status,confirmed_at,confirmed_by,updated_at) ON "{schema}".visits TO "{runtime}"')
            conn.exec_driver_sql(f'CREATE POLICY staff_visit_update ON "{schema}".visits FOR UPDATE TO "{runtime}" USING (true) WITH CHECK (true)')
            conn.exec_driver_sql(f'GRANT USAGE ON SEQUENCE "{schema}".visit_confirmation_generation_seq TO "{runtime}"')
        subject = _module(root / "scripts/provision_confirmation_subject_role.py")
        financial = _module(root / "scripts/provision_encounter_financial_role.py")
        benefit = _module(root / "scripts/provision_encounter_benefit_role.py")
        all_free = _module(root / "scripts/provision_all_free_backend_role.py")
        all_free.provision(admin, schema, runtime, expected_owner=owner, decision_role=decision_cap)
        subject.provision(admin, schema, subject_cap, runtime, expected_owner=owner)
        financial.provision(admin, schema=schema, backend_role=runtime, capability_role=financial_cap, expected_owner=owner)
        benefit.provision(admin, schema=schema, backend_role=runtime, capability_role=financial_cap, expected_owner=owner)
        runtime_engine = sa.create_engine(url.set(username=runtime, password=password),
                                          connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"}, hide_parameters=True)
        for key, value in {
            "TRUSTED_DB_SCHEMA": schema, "TRUSTED_DB_SCHEMA_OWNER": owner, "TRUSTED_DB_RUNTIME_ROLE": runtime,
            "TRUSTED_DB_OWNER_MEMBERS": (), "TRUSTED_AUTH_TABLE_OWNER": owner, "TRUSTED_AUTH_OWNER_MEMBERS": (),
            "TRUSTED_AUTH_READ_ROLES": (), "TRUSTED_AUTH_WRITE_ROLES": (), "TRUSTED_AUTH_USERS_OWNER": owner,
            "TRUSTED_AUTH_USERS_OWNER_MEMBERS": (), "TRUSTED_AUTH_USERS_WRITE_ROLES": (),
        }.items():
            monkeypatch.setattr(settings, key, value)
        with Session(engine, expire_on_commit=False) as db:
            stage_actor = User(username="synthetic-stage-" + suffix, hashed_password="!", role="Admin", is_active=True)
            confirm_actor = User(username="synthetic-confirm-" + suffix, hashed_password="!", role="Registrar", is_active=True)
            patient = Patient(first_name="SYNTHETIC", last_name="SYNTHETIC")
            service = Service(code="SYN" + suffix[:16], name="SYNTHETIC", price=Decimal("10.00"), active=True)
            db.add_all([stage_actor, confirm_actor, patient, service])
            db.flush()
            encounter = Encounter(patient_id=patient.id, provenance="new")
            db.add(encounter)
            db.flush()
            visit = Visit(patient_id=patient.id, encounter_id=encounter.id, visit_date=date(2099, 1, 1),
                          status="pending_confirmation", source="desk")
            db.add(visit)
            db.flush()
            db.add(VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=1, price=Decimal("10.00"), currency="UZS"))
            db.flush()
            db.refresh(visit)
            ids = {"stage": stage_actor.id, "confirm": confirm_actor.id, "visit": visit.id,
                   "epoch": visit.confirmation_context_epoch, "patient": patient.id}
            db.commit()
        # The All Free provisioning can be safely repeated after finance.
        all_free.provision(admin, schema, runtime, expected_owner=owner, decision_role=decision_cap)
        yield engine, runtime_engine, ids
    finally:
        if runtime_engine is not None:
            runtime_engine.dispose()
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(private, cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            for role in (runtime, subject_cap, financial_cap, decision_cap):
                conn.exec_driver_sql(f'DROP OWNED BY "{role}"')
                conn.exec_driver_sql(f'DROP ROLE "{role}"')
        admin.dispose()


def _bearer(user_id):
    return ProfileBearerContext(user_id, 0, "synthetic-jti-" + str(user_id), int(time.time()) + 600, None)


def _stage(db, ids):
    return AllFreeRequestService(db).stage_request(visit_id=ids["visit"], expected_epoch=ids["epoch"], bearer=_bearer(ids["stage"]))


def _confirm(db, ids):
    actor, _ = lock_staff_confirmation_subjects(db, bearer=_bearer(ids["confirm"]), visit_ids=[ids["visit"]])
    VisitLifecycleService(db).confirm_visit(visit_id=ids["visit"], current_user=actor, confirmed_by="synthetic", commit=False)
    db.flush()


def test_cart_receipt_requires_the_issuer_and_current_financial_membership(guarded_pg):
    owner, runtime, ids = guarded_pg
    amount = Decimal("10.00")
    with Session(owner, expire_on_commit=False) as db:
        visit = db.get(Visit, ids["visit"])
        visit.status, visit.approval_status = "confirmed", "approved"
        visit.confirmed_by = f"registrar_{ids['stage']}"
        encounter = db.get(Encounter, visit.encounter_id)
        invoice = PaymentInvoice(
            patient_id=ids["patient"], total_amount=amount,
            registrar_encounter_id_snapshot=encounter.id,
            registrar_encounter_generation_snapshot=encounter.generation,
        )
        db.add(invoice)
        db.flush()
        db.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=amount))
        db.commit()
        receipt = RegistrarCartReceipt(invoice.id, amount, ((visit.id, "confirmed", "approved"),))
        encounter_id = encounter.id

    with Session(runtime) as db:
        db.query(User.id).filter_by(id=ids["stage"]).with_for_update().one()
        assert registrar_cart_receipt_is_current(db, actor_id=ids["stage"], receipt=receipt)
    with Session(runtime) as db:
        db.query(User.id).filter_by(id=ids["confirm"]).with_for_update().one()
        assert not registrar_cart_receipt_is_current(db, actor_id=ids["confirm"], receipt=receipt)
    with Session(owner) as db:
        db.add(Visit(
            patient_id=ids["patient"], encounter_id=encounter_id, visit_date=date(2099, 1, 2),
            status="pending_confirmation", source="desk",
        ))
        db.commit()
    with Session(runtime) as db:
        db.query(User.id).filter_by(id=ids["stage"]).with_for_update().one()
        assert not registrar_cart_receipt_is_current(db, actor_id=ids["stage"], receipt=receipt)


@pytest.mark.parametrize("allow_write", ["explicit_check", "implicit_check"])
def test_all_free_guard_accepts_verified_financial_row_lock_and_rejects_policy_drift(guarded_pg, allow_write):
    engine, runtime, ids = guarded_pg
    with Session(runtime) as db:
        lock_visit_without_pending(db, ids["visit"])
    with Session(engine) as db:
        _stage(db, ids)
        db.commit()
    with Session(runtime) as db:
        with pytest.raises(PendingAllFreeError) as error:
            lock_visit_without_pending(db, ids["visit"])
        assert error.value.status_code == 409
        assert not db.execute(sa.text("""
            SELECT pg_catalog.has_any_column_privilege(CURRENT_USER,'all_free_requests','UPDATE')
        """)).scalar_one()

    with engine.begin() as connection:
        if allow_write == "explicit_check":
            connection.exec_driver_sql("ALTER POLICY financial_cap_update ON all_free_requests WITH CHECK (true)")
        else:
            role = connection.execute(sa.text("""
                SELECT pg_catalog.quote_ident(rolname) FROM pg_catalog.pg_roles
                WHERE oid=(SELECT polroles[1] FROM pg_catalog.pg_policy
                  WHERE polrelid='all_free_requests'::regclass AND polname='financial_cap_update')
            """)).scalar_one()
            connection.exec_driver_sql("DROP POLICY financial_cap_update ON all_free_requests")
            connection.exec_driver_sql(f"CREATE POLICY financial_cap_update ON all_free_requests FOR UPDATE TO {role} USING (true)")
    with Session(runtime) as db:
        with pytest.raises(AllFreeGuardError) as error:
            lock_visit_without_pending(db, ids["visit"])
        assert error.value.status_code == 503


@pytest.mark.parametrize("first", ["stage", "confirm"])
def test_stage_and_staff_confirmation_serialize(guarded_pg, first):
    engine, runtime, ids = guarded_pg
    started, pids = threading.Event(), []
    def compete():
        with Session(runtime if first == "stage" else engine) as db:
            pids.append(db.execute(sa.text("SELECT pg_catalog.pg_backend_pid()" )).scalar_one())
            started.set()
            try:
                (_confirm if first == "stage" else _stage)(db, ids)
                db.commit()
                return "committed"
            except (HTTPException, AllFreeRequestError) as exc:
                db.rollback()
                return exc.status_code
    with Session(engine if first == "stage" else runtime) as holder:
        (_stage if first == "stage" else _confirm)(holder, ids)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(compete)
            assert started.wait(5)
            if first == "stage":
                # financial_lock_rows is NOWAIT: the loser must fail while the
                # pending writer still owns the Visit, before its commit.
                assert future.result(timeout=10) == 409
                holder.commit()
            else:
                # Stage uses a waiting Visit lock. Observe the actual PG lock
                # wait before committing the competing confirmation.
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    assert not future.done()
                    with engine.connect() as conn:
                        if conn.execute(sa.text("SELECT pg_catalog.cardinality(pg_catalog.pg_blocking_pids(:pid))"), {"pid": pids[0]}).scalar_one():
                            break
                    time.sleep(0.02)
                else:
                    pytest.fail("expected PostgreSQL stage lock wait")
                holder.commit()
                assert future.result(timeout=15) == 409
    with Session(engine) as db:
        assert db.get(Visit, ids["visit"]).status == ("pending_confirmation" if first == "stage" else "confirmed")
        assert db.query(AllFreeRequest).count() == (1 if first == "stage" else 0)


def test_logout_lock_and_hidden_blacklist_fail_closed(guarded_pg):
    engine, runtime, ids = guarded_pg
    def attempt():
        with Session(runtime) as db:
            try:
                _confirm(db, ids)
                db.commit()
                return "committed"
            except HTTPException as exc:
                db.rollback()
                return exc.status_code
    with Session(engine) as logout:
        logout.query(User).filter_by(id=ids["confirm"]).with_for_update().one()
        logout.add(TokenBlacklist(jti=_bearer(ids["confirm"]).jti, user_id=ids["confirm"],
            expires_at=datetime.now(UTC) + timedelta(hours=1), reason="logout"))
        logout.flush()
        # No confirmation may pass while individual logout owns User.
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(attempt).result(timeout=10) == 409
        logout.commit()
    assert attempt() == 401
    schema = engine.dialect.default_schema_name
    with engine.begin() as conn:
        conn.exec_driver_sql(f'ALTER POLICY staff_runtime_select ON "{schema}".token_blacklist USING (false)')
    # A hidden revoked row is not proof of an unrevoked session.
    assert attempt() == 503
    with Session(engine) as db:
        assert db.get(Visit, ids["visit"]).status == "pending_confirmation"


@pytest.mark.parametrize("currency_case", ["unknown", "mixed"])
def test_nonowner_staff_rejects_unproven_currency(guarded_pg, currency_case):
    engine, runtime, ids = guarded_pg
    with Session(engine) as db:
        line = db.query(VisitService).filter_by(visit_id=ids["visit"]).one()
        if currency_case == "unknown":
            line.currency = None
        else:
            db.add(VisitService(visit_id=ids["visit"], service_id=line.service_id,
                                name="SYNTHETIC", qty=1, price=Decimal("1.00"), currency="USD"))
        db.commit()
    with Session(runtime) as db:
        with pytest.raises(HTTPException) as exc:
            _confirm(db, ids)
        assert exc.value.status_code == 409
        db.rollback()
    with Session(engine) as db:
        assert db.get(Visit, ids["visit"]).status == "pending_confirmation"

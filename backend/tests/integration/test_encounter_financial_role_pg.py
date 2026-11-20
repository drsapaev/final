"""Disposable real LOGIN tests for financial RLS capability provisioning."""

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
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.db.capability_namespace import capability_schema_name
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
)
from tests.integration.test_encounter_migration_pg import _migration


def _provision_module():
    path = Path(__file__).resolve().parents[3] / "scripts/provision_encounter_financial_role.py"
    spec = importlib.util.spec_from_file_location("financial_role_provision", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.integration
def test_private_functions_are_owned_by_schema_owner_not_migration_login():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    suffix = uuid.uuid4().hex
    schema, owner, migrator = "finowner_" + suffix, "finschemaowner_" + suffix, "finmigrator_" + suffix
    backend, capability = "finruntime_" + suffix, "fincapowner_" + suffix
    private = capability_schema_name(schema)
    password = "synthetic" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        database = conn.execute(text("SELECT current_database()" )).scalar_one()
        quoted_database = conn.dialect.identifier_preparer.quote_identifier(database)
        conn.execute(text(f'CREATE ROLE "{owner}" NOLOGIN'))
        conn.execute(text(f'CREATE ROLE "{migrator}" LOGIN PASSWORD \'{password}\''))
        conn.execute(text(f'CREATE ROLE "{backend}" LOGIN PASSWORD \'{password}\''))
        conn.execute(text(f'CREATE ROLE "{capability}" NOLOGIN'))
        conn.execute(text(f'GRANT "{owner}" TO "{migrator}"'))
        conn.execute(text(f'GRANT CREATE ON DATABASE {quoted_database} TO "{migrator}"'))
        conn.execute(text(f'CREATE SCHEMA "{schema}" AUTHORIZATION "{owner}"'))
    migration_engine = create_engine(url.set(username=migrator, password=password),
                                     connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    try:
        import app.db.base  # noqa: F401
        Base.metadata.create_all(migration_engine)
        with migration_engine.begin() as conn:
            assert conn.execute(text("SELECT current_user")).scalar_one() == migrator
            bootstrap = _migration("0112_doctor_price_context.py")
            bootstrap.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
            bootstrap._bootstrap_capability_namespace(schema)
            conn.execute(text("DROP TABLE encounter_benefit_visit_snapshots"))
            conn.execute(text("DROP INDEX uq_enc_benefit_app_identity"))
            for filename in ("0118_encounter_financial_fence.py", "0125_benefit_visibility.py"):
                migration = _migration(filename)
                migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
                migration.upgrade()
            rows = conn.execute(text("""SELECT p.proname,r.rolname FROM pg_catalog.pg_proc p
              JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
              JOIN pg_catalog.pg_roles r ON r.oid=p.proowner
              WHERE n.nspname=:schema AND p.proname IN
               ('financial_encounter_generation_fence','financial_visit_membership_fence',
                'financial_visit_reference_fence','financial_lock_rows','financial_probe_group','encounter_benefit_quote')
            """), {"schema": private}).all()
            assert len(rows) == 6 and all(row.rolname == owner for row in rows)
        provision = _provision_module()
        with admin.begin() as conn:
            for table in ("encounter_benefit_applications", "encounter_benefit_allocations",
                          "encounter_benefit_events", "encounter_benefit_visit_snapshots", "all_free_requests"):
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" ENABLE ROW LEVEL SECURITY'))
                conn.execute(text(f'ALTER TABLE "{schema}"."{table}" FORCE ROW LEVEL SECURITY'))
            conn.execute(text(f'GRANT SELECT ON "{schema}".all_free_requests TO "{backend}"'))
            conn.execute(text(f'CREATE POLICY allfree_backend_select ON "{schema}".all_free_requests FOR SELECT TO "{backend}" USING (true)'))
        provision.provision(admin, schema=schema, backend_role=backend, capability_role=capability,
                            expected_owner=owner, trusted_owner_members=(migrator,))
        path = Path(__file__).resolve().parents[3] / "scripts/provision_encounter_benefit_role.py"
        spec = importlib.util.spec_from_file_location("benefit_role_owner_test", path)
        benefit_provision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(benefit_provision)
        benefit_provision.provision(admin, schema=schema, backend_role=backend, capability_role=capability,
                                    expected_owner=owner, trusted_owner_members=(migrator,))
    finally:
        migration_engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(private, cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(text(f'REVOKE CREATE ON DATABASE {quoted_database} FROM "{migrator}"'))
            conn.execute(text(f'DROP OWNED BY "{migrator}"'))
            conn.execute(text(f'DROP OWNED BY "{backend}"'))
            conn.execute(text(f'DROP OWNED BY "{capability}"'))
            conn.execute(text(f'DROP OWNED BY "{owner}"'))
            conn.execute(text(f'DROP ROLE "{migrator}"'))
            conn.execute(text(f'DROP ROLE "{backend}"'))
            conn.execute(text(f'DROP ROLE "{capability}"'))
            conn.execute(text(f'DROP ROLE "{owner}"'))
        admin.dispose()


@pytest.mark.integration
def test_real_nonowner_with_forced_rls_detects_hidden_payment(monkeypatch):
    from app.core.config import settings

    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    suffix = uuid.uuid4().hex
    schema, backend, capability, recon_cap = ("finrole_" + suffix, "finback_" + suffix, "fincap_" + suffix, "finrecon_" + suffix)
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
            patient = Patient(first_name="SYNTHETIC", last_name="Financial Role")
            service = Service(code="SYNTHETIC-ROLE", name="SYNTHETIC", price=Decimal("0.07"), active=True)
            db.add_all([patient, service])
            db.flush()
            encounter = Encounter(patient_id=patient.id, provenance="new")
            db.add(encounter)
            db.flush()
            visit = Visit(patient_id=patient.id, encounter_id=encounter.id, status="pending_confirmation", visit_date=date(2099,1,1))
            other = Visit(patient_id=patient.id, encounter_id=encounter.id, status="pending_confirmation", visit_date=date(2099,1,1))
            db.add_all([visit, other])
            db.flush()
            db.add(VisitService(visit_id=visit.id, service_id=service.id, name="SYNTHETIC", qty=3, price=Decimal("0.07"), currency="UZS"))
            db.add(VisitService(visit_id=other.id, service_id=service.id, name="SYNTHETIC", qty=1, price=Decimal("0.00"), currency="UZS"))
            invoice = PaymentInvoice(patient_id=patient.id, total_amount=Decimal("0.21"), status="pending", payment_method="cash", currency="UZS")
            db.add(invoice)
            db.flush()
            db.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=visit.id, visit_amount=Decimal("0.21")))
            db.add(PaymentInvoiceVisit(invoice_id=invoice.id, visit_id=other.id, visit_amount=Decimal("0.00")))
            visit_id, other_id = visit.id, other.id
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
            # Synthetic stand-in for the existing 0114 provisioner, whose
            # all-free policy has the same direct role + true SELECT shape.
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{backend}"'))
            conn.execute(text(f'GRANT SELECT ON "{schema}".all_free_requests TO "{backend}"'))
            conn.execute(text(f'CREATE POLICY allfree_backend_select ON "{schema}".all_free_requests FOR SELECT TO "{backend}" USING (true)'))
        provision.provision(engine, schema=schema, backend_role=backend, capability_role=capability, expected_owner=owner)
        provision.provision(engine, schema=schema, backend_role=backend, capability_role=capability, expected_owner=owner)
        path = Path(__file__).resolve().parents[3] / "scripts/provision_reconciliation_fence_role.py"
        spec = importlib.util.spec_from_file_location("recon_role_provision", path)
        recon_provision = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recon_provision)
        recon_provision.provision(engine, schema=schema, backend_role=backend, capability_role=recon_cap, expected_owner=owner)
        runtime_url = url.set(username=backend, password=password)
        runtime = create_engine(runtime_url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
        private = capability_schema_name(schema)
        with engine.begin() as conn:
            assert not conn.execute(text("""SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_namespace n,
              LATERAL pg_catalog.aclexplode(COALESCE(n.nspacl,pg_catalog.acldefault('n',n.nspowner))) a
              WHERE n.nspname=:ns AND a.grantee=0)"""), {"ns": private}).scalar_one()
            assert not conn.execute(text("SELECT pg_catalog.has_schema_privilege(:role, :ns, 'CREATE')"), {"role": backend, "ns": private}).scalar_one()
            assert not conn.execute(text("""SELECT EXISTS (SELECT 1 FROM pg_catalog.pg_proc p,
              LATERAL pg_catalog.aclexplode(COALESCE(p.proacl,pg_catalog.acldefault('f',p.proowner))) a
              WHERE p.oid=pg_catalog.to_regprocedure(:f) AND a.grantee=0)"""),
                                    {"f": f'"{private}".financial_probe_group(integer)'}).scalar_one()
            # Any public namespace access invalidates the capability even if
            # the configured backend itself still has a direct grant.
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{private}" TO PUBLIC'))
        with Session(runtime) as db:
            with pytest.raises(FinancialFenceError, match="недоступна"):
                lock_financial_group(db, visit_id)
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'REVOKE USAGE ON SCHEMA "{private}" FROM PUBLIC'))
        with Session(runtime) as db:
            assert lock_financial_group(db, visit_id).visits
            db.rollback()
        for key, incorrect in (("TRUSTED_DB_SCHEMA", None),
                               ("TRUSTED_DB_SCHEMA_OWNER", None),
                               ("TRUSTED_DB_RUNTIME_ROLE", None),
                               ("TRUSTED_DB_SCHEMA", "SYNTHETIC_wrong_schema"),
                               ("TRUSTED_DB_SCHEMA_OWNER", "SYNTHETIC_wrong_owner"),
                               ("TRUSTED_DB_RUNTIME_ROLE", "SYNTHETIC_wrong_runtime")):
            previous = getattr(settings, key)
            monkeypatch.setattr(settings, key, incorrect)
            with Session(runtime) as db:
                with pytest.raises(FinancialFenceError, match="недоступна"):
                    lock_financial_group(db, visit_id)
            monkeypatch.setattr(settings, key, previous)
        for signature, replacement in (
            ("financial_visit_membership_fence()", "RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$ BEGIN RETURN NEW; END $$"),
            ("financial_lock_rows(text,integer[])", "(kind text, ids integer[]) RETURNS integer[] LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$ BEGIN RETURN ids; END $$"),
            ("financial_probe_group(integer)", "(encounter_id_input integer) RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on AS $$ BEGIN RETURN '{}'::jsonb; END $$"),
        ):
            function_name = signature.split("(", 1)[0]
            suffix = "() " if signature.endswith("()") else ""
            with engine.begin() as conn:
                original = conn.execute(text("SELECT pg_catalog.pg_get_functiondef(pg_catalog.to_regprocedure(:function))"),
                                        {"function": f'"{private}".{signature}'}).scalar_one()
                conn.execute(text(f'CREATE OR REPLACE FUNCTION "{private}".{function_name}{suffix}{replacement}'))
            try:
                with Session(runtime) as db:
                    with pytest.raises(FinancialFenceError, match="недоступна"):
                        lock_financial_group(db, visit_id)
                with pytest.raises(provision.ProvisionError, match="reviewed contract"):
                    provision.provision(engine, schema=schema, backend_role=backend, capability_role=capability, expected_owner=owner)
            finally:
                with engine.begin() as conn:
                    conn.execute(text(original))
            with Session(runtime) as db:
                assert lock_financial_group(db, visit_id).visits
                db.rollback()
        # A same-named function in the application schema must not replace
        # the reviewed private trigger function, even with the same owner.
        with engine.begin() as conn:
            conn.execute(text(f'GRANT CREATE ON SCHEMA "{schema}" TO "{capability}"'))
            conn.execute(text(f'''CREATE FUNCTION "{schema}".financial_visit_membership_fence()
              RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog SET row_security=on
              AS $$ BEGIN RETURN NEW; END $$'''))
            conn.execute(text(f'ALTER FUNCTION "{schema}".financial_visit_membership_fence() OWNER TO "{capability}"'))
            conn.execute(text(f'REVOKE ALL ON FUNCTION "{schema}".financial_visit_membership_fence() FROM PUBLIC'))
            conn.execute(text(f'REVOKE CREATE ON SCHEMA "{schema}" FROM "{capability}"'))
            conn.execute(text(f'DROP TRIGGER trg_financial_visit_membership ON "{schema}".visits'))
            conn.execute(text(f'''CREATE TRIGGER trg_financial_visit_membership AFTER INSERT OR UPDATE OR DELETE
              ON "{schema}".visits FOR EACH ROW EXECUTE FUNCTION "{schema}".financial_visit_membership_fence()'''))
        try:
            with Session(runtime) as db:
                with pytest.raises(FinancialFenceError, match="недоступна"):
                    lock_financial_group(db, visit_id)
            with pytest.raises(provision.ProvisionError, match="reviewed contract"):
                provision.provision(engine, schema=schema, backend_role=backend, capability_role=capability, expected_owner=owner)
        finally:
            with engine.begin() as conn:
                conn.execute(text(f'DROP TRIGGER trg_financial_visit_membership ON "{schema}".visits'))
                conn.execute(text(f'''CREATE TRIGGER trg_financial_visit_membership AFTER INSERT OR UPDATE OR DELETE
                  ON "{schema}".visits FOR EACH ROW EXECUTE FUNCTION "{private}".financial_visit_membership_fence()'''))
                conn.execute(text(f'DROP FUNCTION "{schema}".financial_visit_membership_fence()'))
        with Session(runtime) as db:
            db.execute(text("CREATE TEMP TABLE payments (id integer, visit_id integer)"))
            db.execute(text(f'SET LOCAL search_path TO pg_catalog, "{schema}", pg_temp'))
            group = lock_financial_group(db, visit_id)
            assert group.visits
            db.execute(text(f'SET LOCAL search_path TO pg_catalog, pg_temp, "{schema}"'))
            with pytest.raises(FinancialFenceError, match="недоступна"):
                lock_financial_group(db, visit_id)
            db.rollback()
        with Session(runtime) as db:
            who = db.execute(text("SELECT CURRENT_USER, SESSION_USER")).one()
            assert who == (backend, backend)
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(text(f'SET LOCAL ROLE "{capability}"'))
            group = lock_financial_group(db, visit_id)
            requote_draft_invoices(group, {visit_id: Decimal("0.11"), other_id: Decimal("0.00")})
            db.commit()
        with engine.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".payment_invoices SET total_amount=0.21'))
            conn.execute(text(f'UPDATE "{schema}".payment_invoice_visits SET visit_amount=0.21 WHERE visit_id=:visit'), {"visit": visit_id})
        with Session(engine) as db:
            rows = []
            for target in (visit_id, other_id):
                current = db.get(Visit, target)
                row = AllFreeRequest(visit_id=target, patient_id=current.patient_id, encounter_id=current.encounter_id,
                    visit_id_snapshot=target, patient_id_snapshot=current.patient_id, encounter_id_snapshot=current.encounter_id,
                    visit_context_epoch=1, baseline_total=Decimal("0.21"), status="pending",
                    requested_by_user_id_snapshot=1, requested_by_role_snapshot="admin", policy_auto_approve=False)
                db.add(row)
                rows.append(row)
            db.flush()
            first_request, second_request = [r.id for r in rows]
            db.commit()
        with Session(runtime) as db:
            selected = lock_financial_group(db, visit_id, allow_all_free_request_id=first_request)
            assert {r.id for r in selected.pending_requests} == {first_request, second_request}
            def competing():
                with Session(runtime) as other:
                    try:
                        lock_financial_group(other, other_id, allow_all_free_request_id=second_request)
                    except DBAPIError as exc:
                        other.rollback()
                        return getattr(exc.orig, "sqlstate", None)
                    return "unexpected-success"
            with ThreadPoolExecutor(max_workers=1) as pool:
                assert pool.submit(competing).result(timeout=10) == "55P03"
            with pytest.raises(FinancialFenceError, match="заявка"):
                lock_group_without_pending(db, visit_id)
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'ALTER POLICY allfree_backend_select ON "{schema}".all_free_requests USING (false)'))
        with Session(runtime) as db:
            with pytest.raises(FinancialFenceError, match="недоступна"):
                lock_financial_group(db, visit_id, allow_all_free_request_id=first_request)
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'ALTER POLICY allfree_backend_select ON "{schema}".all_free_requests USING (true)'))
            conn.execute(text(f'ALTER TABLE "{schema}".visits DISABLE TRIGGER trg_financial_visit_membership'))
        with Session(runtime) as db:
            with pytest.raises(FinancialFenceError, match="недоступна"):
                lock_financial_group(db, visit_id, allow_all_free_request_id=first_request)
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'ALTER TABLE "{schema}".visits ENABLE TRIGGER trg_financial_visit_membership'))
        with engine.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".all_free_requests SET status=\'invalidated\' WHERE id=:id'), {"id": first_request})
        with Session(runtime) as db:
            with pytest.raises(FinancialFenceError, match="заявка"):
                lock_group_without_pending(db, visit_id)
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'UPDATE "{schema}".all_free_requests SET status=\'invalidated\' WHERE id=:id'), {"id": second_request})
        with Session(engine) as db:
            db.add(Payment(visit_id=visit_id, amount=Decimal("0.11"), status="pending", method="online", provider="click", currency="UZS"))
            db.commit()
        with Session(runtime) as db:
            # Payment guard only checks pending All Free; it must not treat an
            # otherwise legitimate prior payment as a pending request.
            lock_group_without_pending(db, visit_id)
            db.rollback()
        with Session(runtime) as db:
            with pytest.raises(FinancialFenceError, match="Платежи"):
                lock_financial_group(db, visit_id)
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'ALTER POLICY financial_cap_select ON "{schema}".provider_attempt_visits USING (false)'))
        with Session(runtime) as db:
            with pytest.raises(DBAPIError):
                lock_financial_group(db, visit_id)
            db.rollback()
        with engine.begin() as conn:
            conn.execute(text(f'ALTER POLICY financial_cap_select ON "{schema}".provider_attempt_visits USING (true)'))
            conn.execute(text(f'ALTER POLICY financial_backend_select ON "{schema}".visit_services USING (false)'))
        with Session(runtime) as db:
            with pytest.raises(FinancialFenceError):
                lock_financial_group(db, visit_id)
            db.rollback()
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

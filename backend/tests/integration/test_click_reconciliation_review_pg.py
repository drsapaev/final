"""Synthetic migration-login/schema-owner split for Click capabilities."""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import DropSchema

from app.db.capability_namespace import capability_schema_name
from app.services.click_receipt_service import ClickReceiptError, ClickReceiptService
from tests.integration.test_click_receipt_pg import KEY, PAYLOAD, SECRET

_ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, _ROOT / path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.mark.integration
def test_distinct_migration_login_keeps_schema_owner_and_exact_membership():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex[:12]
    schema, owner_role, migrator, backend, cap = (f"clickown_{suffix}", f"clickowner_{suffix}",
        f"clickmigrator_{suffix}", f"clickbackend_{suffix}", f"clickcap_{suffix}")
    password = f"synthetic_{suffix}"
    private = capability_schema_name(schema)
    admin = create_engine(url)
    migrate = create_engine(url.set(username=migrator, password=password), connect_args={"options": f"-csearch_path={schema}"})
    runtime = create_engine(url.set(username=backend, password=password), connect_args={"options": f"-csearch_path={schema}"})
    quote = admin.dialect.identifier_preparer.quote_identifier
    qdb, qs, qp = quote(url.database), quote(schema), quote(private)
    try:
        with admin.begin() as db:
            db.exec_driver_sql(f'CREATE ROLE "{owner_role}" NOLOGIN')
            db.exec_driver_sql(f'CREATE ROLE "{migrator}" LOGIN PASSWORD \'{password}\'')
            db.exec_driver_sql(f'CREATE ROLE "{backend}" LOGIN PASSWORD \'{password}\'')
            db.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
            db.exec_driver_sql(f'GRANT "{owner_role}" TO "{migrator}"')
            db.exec_driver_sql(f'GRANT CREATE ON DATABASE {qdb} TO "{owner_role}"')
            db.exec_driver_sql(f'CREATE SCHEMA {qs} AUTHORIZATION "{owner_role}"')
            db.exec_driver_sql(f'SET LOCAL ROLE "{owner_role}"')
            db.execute(text("SELECT pg_catalog.set_config('search_path', :schema, true)"), {"schema": qs})
            for table in ("payments", "payment_invoices", "payment_webhooks", "users", "visits"):
                db.execute(text(f"CREATE TABLE {table} (id integer PRIMARY KEY)"))
            m109 = load("click_owner_0109", "backend/alembic/versions/0109_provider_reconciliation.py")
            m109.op = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema}))
            m109.upgrade()
            m111 = load("click_owner_0111", "backend/alembic/versions/0111_provider_attempts.py")
            m111.op = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema}))
            m111.upgrade()
        with migrate.begin() as db:
            operations = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema}))
            m119 = load("click_owner_0119", "backend/alembic/versions/0119_click_receipt.py")
            m119.op = operations
            m119.upgrade()
            m112 = load("click_owner_0112", "backend/alembic/versions/0112_doctor_price_context.py")
            m112.op = operations
            m112._bootstrap_capability_namespace(schema)
            for name in ("0123_reconciliation_fence.py", "0127_click_phase_binding.py", "0129_click_reconciliation.py"):
                module = load("click_owner_" + name[:4], "backend/alembic/versions/" + name)
                module.op = operations
                module.upgrade()
        with admin.connect() as db:
            tables = ("click_receipt_key_versions", "click_callback_receipts", "provider_reconciliation_mutex",
                      "click_issued_attempts", "click_prepares", "click_receipt_reconciliation_links", "click_reconciliation_reviews")
            assert db.execute(text("""SELECT count(*) FROM pg_catalog.pg_class c JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
              JOIN pg_catalog.pg_roles o ON o.oid=c.relowner WHERE n.nspname=:schema AND c.relname=ANY(:tables) AND o.rolname=:owner"""),
              {"schema": schema, "tables": list(tables), "owner": owner_role}).scalar_one() == len(tables)
            assert db.execute(text("""SELECT count(*) FROM pg_catalog.pg_proc p JOIN pg_catalog.pg_namespace n ON n.oid=p.pronamespace
              JOIN pg_catalog.pg_roles o ON o.oid=p.proowner WHERE n.nspname=:schema
              AND p.proname IN ('reconciliation_mutex_lock','reconciliation_pending_guard','click_review_mutex_lock') AND o.rolname=:owner"""),
              {"schema": private, "owner": owner_role}).scalar_one() == 3
        rp = load("click_owner_receipt_provision", "scripts/provision_click_receipt_role.py")
        fp = load("click_owner_fence_provision", "scripts/provision_reconciliation_fence_role.py")
        pp = load("click_owner_phase_provision", "scripts/provision_click_phase_role.py")
        allowed = (migrator,)
        rp.provision(admin, schema=schema, owner=owner_role, role=backend, version="v1", key=KEY, trusted_owner_members=allowed)
        fp.provision(admin, schema=schema, expected_owner=owner_role, backend_role=backend, capability_role=cap, trusted_owner_members=allowed)
        pp.provision(admin, schema=schema, owner=owner_role, backend_role=backend, trusted_owner_members=allowed)
        with admin.begin() as db:
            db.execute(text(f"INSERT INTO {qs}.payment_webhooks(id) VALUES (1)"))
            db.execute(text(f"""INSERT INTO {qs}.provider_reconciliation_events
              (provider,source,phase,event_key,provider_reference_digest,target_kind,webhook_id,webhook_id_snapshot,
               amount_minor,currency,currency_exponent,observed_status,evidence_sha256,verified_at)
              VALUES ('click','poll','complete',:key,:digest,'unmatched',1,1,'1234','UZS',2,'unknown',:digest,now())"""),
              {"key": "a" * 64, "digest": "b" * 64})
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(text(f"UPDATE {qs}.provider_reconciliation_events SET amount_minor='9999'"))
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(text(f"DELETE FROM {qs}.provider_reconciliation_events"))
            db.execute(text(f"DELETE FROM {qs}.payment_webhooks WHERE id=1"))
            assert db.execute(text(f"SELECT webhook_id,webhook_id_snapshot FROM {qs}.provider_reconciliation_events")).one() == (None, 1)
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(text(f"UPDATE {qs}.provider_reconciliation_events SET webhook_id=1"))
        with Session(runtime) as db:
            stored = ClickReceiptService(db, keyring={"v1": KEY}, active_version="v1", trusted_schema=schema,
                trusted_owner=owner_role, trusted_owner_members=allowed).store(body=PAYLOAD,
                  content_type="application/x-www-form-urlencoded", service_id="100", secret_key=SECRET)
            assert stored.created
        with runtime.begin() as db:
            assert db.exec_driver_sql(f"SELECT {qp}.reconciliation_pending_guard()").scalar_one() is True
        with Session(runtime) as db:
            with pytest.raises(ClickReceiptError, match="role unavailable"):
                ClickReceiptService(db, keyring={"v1": KEY}, active_version="v1", trusted_schema=schema,
                    trusted_owner=owner_role).store(body=PAYLOAD, content_type="application/x-www-form-urlencoded",
                                                     service_id="100", secret_key=SECRET)
    finally:
        runtime.dispose()
        migrate.dispose()
        with admin.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            db.execute(DropSchema(private, cascade=True, if_exists=True))
            if db.execute(text("SELECT EXISTS(SELECT 1 FROM pg_catalog.pg_roles WHERE rolname=:role)"), {"role": owner_role}).scalar_one():
                db.exec_driver_sql(f'REVOKE CREATE ON DATABASE {qdb} FROM "{owner_role}"')
            for role in (backend, cap, migrator, owner_role):
                db.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
        admin.dispose()

"""Synthetic trigger races for 0118; not a complete Alembic or API test."""

import io
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.capability_namespace import capability_schema_name
from tests.integration.test_encounter_migration_pg import _migration


def test_offline_quote_delimiter_avoids_hostile_schema_identifier():
    output = io.StringIO()
    schema = "synthetic'_$financial_capability$"
    migration = _migration("0118_encounter_financial_fence.py")
    assert migration._capability_schema_name(schema) == capability_schema_name(schema)
    assert _migration("0125_benefit_visibility.py")._capability_schema_name(schema) == capability_schema_name(schema)
    assert _migration("0112_doctor_price_context.py")._capability_schema_name(schema) == capability_schema_name(schema)
    migration.op = Operations(MigrationContext.configure(
        url="postgresql://", opts={"as_sql": True, "output_buffer": output, "version_table_schema": schema}
    ))
    migration.upgrade()
    sql = output.getvalue()
    assert f'{capability_schema_name(schema)}.financial_probe_group' in sql
    assert "AS $financial_capability_1$" in sql
    assert "synthetic''_$financial_capability$" in sql


@pytest.fixture
def case():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    schema = "finance_fence_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        bootstrap = _migration("0112_doctor_price_context.py")
        bootstrap.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
        bootstrap._bootstrap_capability_namespace(schema)
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=5000"})
    try:
        with engine.begin() as conn:
            for sql in (
                "CREATE TABLE encounters (id integer PRIMARY KEY, patient_id integer, generation bigint NOT NULL DEFAULT 1)",
                "CREATE TABLE visits (id integer PRIMARY KEY, patient_id integer, encounter_id integer REFERENCES encounters(id))",
                "CREATE TABLE payment_invoices (id integer PRIMARY KEY, status text)",
                "CREATE TABLE payment_invoice_visits (id integer PRIMARY KEY, invoice_id integer REFERENCES payment_invoices(id), visit_id integer REFERENCES visits(id), visit_amount numeric(12,2))",
                "CREATE TABLE payments (id integer PRIMARY KEY, visit_id integer REFERENCES visits(id), status text)",
                "CREATE TABLE payment_visits (id integer PRIMARY KEY, visit_id integer REFERENCES visits(id))",
                "CREATE TABLE payment_webhooks (id integer PRIMARY KEY, visit_id integer)",
                "CREATE TABLE payment_transactions (id integer PRIMARY KEY, visit_id integer)",
                "CREATE TABLE invoices (id integer PRIMARY KEY, visit_id integer REFERENCES visits(id))",
                "INSERT INTO encounters VALUES (1, 1, 5000000000000000)",
                "INSERT INTO visits VALUES (1, 1, 1)",
                "INSERT INTO payment_invoices VALUES (1, 'pending')",
                "INSERT INTO payment_invoice_visits VALUES (1, 1, 1, 0)",
            ):
                conn.execute(text(sql))
            migration = _migration("0118_encounter_financial_fence.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(capability_schema_name(schema), cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_membership_and_encounter_identity_never_reuse_generation(case):
    with case.begin() as conn:
        before = conn.execute(text("SELECT generation FROM encounters WHERE id=1")).scalar_one()
        assert before == 5000000000000000
        conn.execute(text("SELECT pg_catalog.setseed(0.25)"))
        conn.execute(text("INSERT INTO visits VALUES (2,1,1)"))
        changed = conn.execute(text("SELECT generation FROM encounters WHERE id=1")).scalar_one()
        assert changed > before
        conn.execute(text("SELECT pg_catalog.setseed(0.25)"))
        conn.execute(text("DELETE FROM visits WHERE id=2"))
        assert conn.execute(text("SELECT generation FROM encounters WHERE id=1")).scalar_one() > changed
        conn.execute(text("INSERT INTO encounters (id, patient_id) VALUES (2, 1)"))
        previous = conn.execute(text("SELECT generation FROM encounters WHERE id=2")).scalar_one()
        conn.execute(text("DELETE FROM encounters WHERE id=2"))
        conn.execute(text("INSERT INTO encounters (id, patient_id) VALUES (2, 1)"))
        assert conn.execute(text("SELECT generation FROM encounters WHERE id=2")).scalar_one() > previous
        with pytest.raises(DBAPIError), conn.begin_nested():
            conn.execute(text("UPDATE encounters SET generation=:old WHERE id=1"), {"old": before})
        migration = _migration("0118_encounter_financial_fence.py")
        migration.op = Operations(MigrationContext.configure(conn))
        with pytest.raises(RuntimeError, match="requires an audited rollback"):
            migration.downgrade()
        migration.upgrade()
        conn.execute(text("INSERT INTO visits VALUES (3,1,1)"))
        assert conn.execute(text("SELECT generation FROM encounters WHERE id=1")).scalar_one() > changed


@pytest.mark.parametrize("sql", [
    "INSERT INTO visits VALUES (2,1,1)",
    "INSERT INTO payment_invoice_visits VALUES (2,1,1,0)",
    "INSERT INTO payments VALUES (1,1,'pending')",
    "UPDATE payment_invoices SET status='processing' WHERE id=1",
    "INSERT INTO invoices VALUES (1,1)",
])
def test_competing_mutation_fails_fast_while_visit_locked(case, sql):
    with case.connect() as holder:
        transaction = holder.begin()
        holder.execute(text("SELECT id FROM visits WHERE id=1 FOR UPDATE"))
        holder.execute(text("SELECT id FROM encounters WHERE id=1 FOR UPDATE"))
        def competing():
            try:
                with case.begin() as conn:
                    conn.execute(text(sql))
            except DBAPIError as exc:
                return getattr(exc.orig, "sqlstate", None)
            return "committed"
        with ThreadPoolExecutor(max_workers=1) as executor:
            try:
                assert executor.submit(competing).result(timeout=8) == "55P03"
            finally:
                transaction.rollback()


def test_invoice_link_writer_first_then_reader_sees_new_membership(case):
    with case.connect() as writer:
        tx = writer.begin()
        writer.execute(text("INSERT INTO payment_invoice_visits VALUES (2,1,1,0)"))
        started = threading.Event()
        def reader():
            with case.begin() as conn:
                started.set()
                conn.execute(text("SELECT id FROM visits WHERE id=1 FOR UPDATE"))
                conn.execute(text("SELECT id FROM encounters WHERE id=1 FOR UPDATE"))
                return conn.execute(text("SELECT count(*) FROM payment_invoice_visits WHERE invoice_id=1")).scalar_one()
        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(reader)
            assert started.wait(5)
            time.sleep(0.1)
            assert not future.done()
            tx.commit()
            assert future.result(timeout=8) == 2


def test_local_fk_timeout_rolls_back_and_does_not_leak_to_pool(case):
    with case.connect() as holder:
        transaction = holder.begin()
        holder.execute(text("SELECT id FROM visits WHERE id=1 FOR UPDATE"))
        with case.connect() as candidate:
            other_tx = candidate.begin()
            candidate.execute(text("SET LOCAL lock_timeout='100ms'"))
            try:
                with pytest.raises(DBAPIError) as error:
                    candidate.execute(text("INSERT INTO payment_invoice_visits VALUES (2,1,1,0)"))
                assert getattr(error.value.orig, "sqlstate", None) == "55P03"
            finally:
                other_tx.rollback()
                transaction.rollback()
            assert candidate.execute(text("SHOW lock_timeout")).scalar_one() == "5s"
            assert candidate.execute(text("SELECT count(*) FROM payment_invoice_visits WHERE id=2")).scalar_one() == 0


def test_nonowner_shadow_path_cannot_redirect_trigger_or_set_sequence(case):
    suffix = uuid.uuid4().hex
    role, shadow = "finance_role_" + suffix, "finance_shadow_" + suffix
    try:
        with case.begin() as conn:
            trusted = conn.execute(text("SELECT current_schema()")).scalar_one()
            conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
            conn.execute(CreateSchema(shadow))
            conn.execute(text(f'CREATE TABLE "{shadow}".encounters (id integer, generation bigint)'))
            conn.execute(text(f'INSERT INTO "{shadow}".encounters VALUES (1, 7)'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{trusted}", "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{trusted}" TO "{role}"'))
            conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{shadow}", "{trusted}", pg_catalog'))
            conn.execute(text(f'INSERT INTO "{trusted}".visits VALUES (2,1,1)'))
            assert conn.execute(text(f'SELECT generation FROM "{trusted}".encounters WHERE id=1')).scalar_one() > 5000000000000000
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text(f"SELECT pg_catalog.setval('\"{trusted}\".encounter_financial_generation_seq', 1)"))
            conn.execute(text("RESET ROLE"))
            assert conn.execute(text(f'SELECT generation FROM "{shadow}".encounters WHERE id=1')).scalar_one() == 7
    finally:
        with case.begin() as conn:
            conn.execute(text(f'DROP OWNED BY "{role}"'))
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))

"""0116 operates on 0102/0115 credentials without trusting the search path."""

import io
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.capability_namespace import capability_schema_name
from tests.integration.test_encounter_migration_pg import _migration
from tests.integration.test_visit_confirmation_context_pg import _create_table
from tests.integration.test_visit_confirmation_context_pg import (
    _migration as _old_migration,
)


def _apply(conn, migration):
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    return migration


def _setup(conn):
    conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    conn.execute(text("INSERT INTO users(id) VALUES (1),(2)"))
    _create_table(conn)
    conn.execute(text("ALTER TABLE patients ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE SET NULL"))
    conn.execute(text("ALTER TABLE patients ADD COLUMN is_deleted INTEGER NOT NULL DEFAULT 0"))
    conn.execute(text("UPDATE patients SET user_id=1 WHERE id=1"))
    conn.execute(text("INSERT INTO patients(id,phone,user_id) VALUES (2,'synthetic',2)"))
    conn.execute(text("INSERT INTO visits(id,patient_id,status,confirmation_token) VALUES (2,2,'pending_confirmation','other-token')"))
    conn.execute(text("INSERT INTO visits(id,patient_id,status,confirmation_token) VALUES (3,1,'open','ticket-qr-hash')"))
    _apply(conn, _old_migration())
    _apply(conn, _migration("0115_confirmation_trigger_path.py"))
    if conn.dialect.name == "postgresql":
        bootstrap = _migration("0112_doctor_price_context.py")
        bootstrap.op = Operations(MigrationContext.configure(conn))
        bootstrap._bootstrap_capability_namespace(conn.dialect.default_schema_name)
    _apply(conn, _migration("0116_patient_owner_confirmation.py"))


def _snapshot(conn, visit_id):
    return conn.execute(text("SELECT confirmation_token, confirmation_expires_at, confirmation_context_epoch, reminder_generation FROM visits WHERE id=:id"), {"id": visit_id}).one()


def test_offline_schema_quotes_cannot_escape_function_body():
    output = io.StringIO()
    schema = "owner_'$owner_confirmation_0$_$owner_confirmation_1$"
    migration = _migration("0116_patient_owner_confirmation.py")
    migration.op = Operations(MigrationContext.configure(url="postgresql://", opts={
        "as_sql": True, "output_buffer": output, "version_table_schema": schema,
    }))
    migration.upgrade()
    sql = output.getvalue()
    assert "AS $owner_confirmation_2$" in sql
    assert "owner_''$owner_confirmation_0$" in sql


@pytest.mark.parametrize("schema", ["public", "SYNTHETIC_'quoted", "клиника"])
def test_frozen_private_namespace_matches_runtime(schema):
    migration = _migration("0116_patient_owner_confirmation.py")
    assert migration._capability_schema_name(schema) == capability_schema_name(schema)


@pytest.mark.integration
def test_postgres_backslash_schema_with_legacy_string_setting():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql" or not (make_url(raw).database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    schema = "owner_\\'_" + uuid.uuid4().hex
    private = capability_schema_name(schema)
    engine = create_engine(raw)
    quoted = engine.dialect.identifier_preparer.quote_identifier(schema)
    try:
        with engine.begin() as conn:
            conn.execute(CreateSchema(schema))
            conn.execute(text(f"CREATE TABLE {quoted}.patients (id integer PRIMARY KEY, user_id integer, is_deleted boolean NOT NULL DEFAULT false)"))
            conn.execute(text(f"CREATE TABLE {quoted}.visits (id integer PRIMARY KEY, patient_id integer, status text, confirmation_token text, confirmation_expires_at timestamp, confirmation_context_epoch bigint, reminder_sent_at timestamp, reminder_generation integer)"))
            conn.execute(text(f"CREATE SEQUENCE {quoted}.visit_confirmation_generation_seq"))
            conn.execute(text(f"INSERT INTO {quoted}.patients (id,user_id) VALUES (1,1)"))
            conn.execute(text(f"INSERT INTO {quoted}.visits (id,patient_id,status,confirmation_token) VALUES (1,1,'pending_confirmation','synthetic-token')"))
            bootstrap = _migration("0112_doctor_price_context.py")
            bootstrap.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
            bootstrap._bootstrap_capability_namespace(schema)
            conn.execute(text("SET LOCAL standard_conforming_strings=off"))
            migration = _migration("0116_patient_owner_confirmation.py")
            migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
            migration.upgrade()
            assert conn.execute(text("SHOW standard_conforming_strings")).scalar_one() == "off"
            conn.execute(text(f"UPDATE {quoted}.patients SET user_id=2 WHERE id=1"))
            assert conn.execute(text(f"SELECT confirmation_token FROM {quoted}.visits WHERE id=1")).scalar_one() is None
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True, if_exists=True))
            conn.execute(DropSchema(private, cascade=True, if_exists=True))
        engine.dispose()


def _exercise(conn):
    before = _snapshot(conn, 1)
    other = _snapshot(conn, 2)
    conn.execute(text("UPDATE patients SET user_id=user_id, is_deleted=is_deleted WHERE id=1"))
    assert _snapshot(conn, 1) == before
    conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
    after = _snapshot(conn, 1)
    assert after.confirmation_token is None and after.confirmation_expires_at is None
    assert after.confirmation_context_epoch > before.confirmation_context_epoch
    assert _snapshot(conn, 3).confirmation_token is None
    assert _snapshot(conn, 2) == other
    conn.execute(text("UPDATE visits SET confirmation_token='replacement' WHERE id=1"))
    conn.execute(text("UPDATE patients SET user_id=1 WHERE id=1"))
    returned = _snapshot(conn, 1)
    assert returned.confirmation_token is None
    assert returned.confirmation_context_epoch > after.confirmation_context_epoch
    conn.execute(text("UPDATE visits SET confirmation_token='new' WHERE id=1"))
    conn.execute(text("DELETE FROM users WHERE id=1"))
    assert conn.execute(text("SELECT user_id FROM patients WHERE id=1")).scalar_one() is None
    assert _snapshot(conn, 1).confirmation_token is None
    conn.execute(text("UPDATE visits SET confirmation_token='next' WHERE id=1"))
    with conn.begin_nested() as savepoint:
        conn.execute(text("UPDATE patients SET is_deleted=1 WHERE id=1"))
        assert _snapshot(conn, 1).confirmation_token is None
        savepoint.rollback()
    assert _snapshot(conn, 1).confirmation_token == 'next'
    conn.execute(text("UPDATE patients SET is_deleted=1 WHERE id=1"))
    assert _snapshot(conn, 1).confirmation_token is None


@pytest.mark.parametrize("recursive", [0, 1])
def test_sqlite_owner_change_and_downgrade_preserve_fence(recursive):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("PRAGMA foreign_keys=ON")
            conn.exec_driver_sql(f"PRAGMA recursive_triggers={recursive}")
            _setup(conn)
            _exercise(conn)
            migration = _migration("0116_patient_owner_confirmation.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.downgrade()
            migration.upgrade()
            conn.execute(text("UPDATE visits SET confirmation_token='after-rollback' WHERE id=1"))
            conn.execute(text("UPDATE patients SET is_deleted=0 WHERE id=1"))
            assert _snapshot(conn, 1).confirmation_token is None
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgres_nonowner_shadow_schema_and_owner_change():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex
    trusted, shadow, role = "owner_real_" + suffix, "owner_shadow_" + suffix, "owner_role_" + suffix
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(trusted))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={trusted}"})
    try:
        with engine.begin() as conn:
            _setup(conn)
            conn.execute(text(f'CREATE TABLE "{shadow}".visits AS SELECT * FROM "{trusted}".visits'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{trusted}", "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{trusted}", "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT USAGE ON ALL SEQUENCES IN SCHEMA "{trusted}" TO "{role}"'))
            conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{shadow}", "{trusted}", pg_catalog'))
            conn.execute(text(f'UPDATE "{trusted}".patients SET user_id=2 WHERE id=1'))
            assert conn.execute(text(f'SELECT confirmation_token FROM "{trusted}".visits WHERE id=1')).scalar_one() is None
            assert conn.execute(text(f'SELECT confirmation_token FROM "{shadow}".visits WHERE id=1')).scalar_one() == 'original-token'
            conn.execute(text(f'UPDATE "{trusted}".patients SET user_id=1 WHERE id=1'))
            conn.execute(text(f"UPDATE \"{trusted}\".visits SET confirmation_token='original-token' WHERE id=1"))
            conn.execute(text(f'SET LOCAL search_path TO "{trusted}", "{shadow}", pg_catalog'))
            _exercise(conn)
            conn.execute(text("RESET ROLE"))
            # A runtime role subject to a partial RLS view cannot silently
            # approve the owner change while skipping hidden visits.
            conn.execute(text(f'ALTER TABLE "{trusted}".visits ENABLE ROW LEVEL SECURITY'))
            conn.execute(text(f'CREATE POLICY partial_visit_visibility ON "{trusted}".visits TO "{role}" USING (id=2) WITH CHECK (id=2)'))
            conn.execute(text(f'UPDATE "{trusted}".patients SET is_deleted=0 WHERE id=1'))
            conn.execute(text(f"UPDATE \"{trusted}\".visits SET confirmation_token='must-survive-rollback' WHERE id=1"))
            conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            with pytest.raises(DBAPIError), conn.begin_nested():
                conn.execute(text(f'UPDATE "{trusted}".patients SET is_deleted=1 WHERE id=1'))
            conn.execute(text("RESET ROLE"))
            assert conn.execute(text(f'SELECT is_deleted FROM "{trusted}".patients WHERE id=1')).scalar_one() == 0
            assert conn.execute(text(f'SELECT confirmation_token FROM "{trusted}".visits WHERE id=1')).scalar_one() == 'must-survive-rollback'
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(trusted, cascade=True))
            conn.execute(DropSchema(capability_schema_name(trusted), cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()

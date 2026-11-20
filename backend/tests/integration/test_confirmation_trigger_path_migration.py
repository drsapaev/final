"""Apply 0115 to existing 0102 and exercise nonowner shadow search_path."""

import io
import os
import uuid

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

from tests.integration.test_encounter_migration_pg import _migration, _setup_0103
from tests.integration.test_visit_confirmation_context_pg import _create_table
from tests.integration.test_visit_confirmation_context_pg import (
    _migration as _old_migration,
)


@pytest.mark.integration
def test_replaces_existing_functions_without_changing_owner_or_acl():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex
    trusted, shadow, role = "confirm_real_" + suffix, "confirm_shadow_" + suffix, "confirm_role_" + suffix
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(trusted))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={trusted} -clock_timeout=10000"})
    try:
        with engine.begin() as conn:
            _setup_0103(conn)
        # The vulnerable 0102 functions are committed before this migration,
        # modelling an existing installation rather than fresh-only DDL.
        with engine.begin() as conn:
            function_names = ["invalidate_visit_confirmation_context", "invalidate_visit_service_confirmation", "invalidate_patient_phone_confirmations"]
            for name in function_names:
                conn.execute(text(f'REVOKE EXECUTE ON FUNCTION "{trusted}"."{name}"() FROM PUBLIC'))
                conn.execute(text(f'GRANT EXECUTE ON FUNCTION "{trusted}"."{name}"() TO "{role}"'))
            def metadata():
                return conn.execute(text("""
                    SELECT p.proname,p.proowner,p.proacl::text FROM pg_proc p
                    JOIN pg_namespace n ON n.oid=p.pronamespace
                    WHERE n.nspname=:schema AND p.proname = ANY(:names) ORDER BY p.proname
                """), {"schema": trusted, "names": function_names}).all()

            before = metadata()
            assert len(before) == 3
            # Existing nonstandard epochs must neither be rewritten nor
            # exceeded by a random-only high-water assumption.
            conn.execute(text(f'ALTER TABLE "{trusted}".visits DISABLE TRIGGER trg_visit_confirmation_context'))
            conn.execute(text(f"UPDATE \"{trusted}\".visits SET confirmation_context_epoch=5000000000000000, confirmation_token='live' WHERE id=1"))
            conn.execute(text(f'ALTER TABLE "{trusted}".visits ENABLE TRIGGER trg_visit_confirmation_context'))
            migration = _migration("0115_confirmation_trigger_path.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            assert metadata() == before
            assert conn.execute(text(f'SELECT confirmation_context_epoch, confirmation_token FROM "{trusted}".visits WHERE id=1')).one() == (5000000000000000, 'live')
            conn.execute(text(f'CREATE TABLE "{shadow}".visits AS SELECT * FROM "{trusted}".visits'))
            conn.execute(text(f'CREATE FUNCTION "{shadow}".random() RETURNS double precision LANGUAGE sql IMMUTABLE AS $$ SELECT 0::double precision $$'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{trusted}", "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT USAGE ON SEQUENCE "{trusted}".visit_confirmation_generation_seq TO "{role}"'))
            conn.execute(text(f'GRANT USAGE ON SEQUENCE "{trusted}".repeat_evidence_generation_seq TO "{role}"'))
            conn.execute(text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{trusted}", "{shadow}" TO "{role}"'))
            conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{shadow}", "{trusted}", pg_catalog'))
            conn.execute(text('SELECT pg_catalog.setseed(0.25)'))
            conn.execute(text(f"UPDATE \"{trusted}\".visits SET status='pending_confirmation' WHERE id IN (1,2)"))
            first = conn.execute(text(f'SELECT confirmation_context_epoch FROM "{trusted}".visits WHERE id=1')).scalar_one()
            assert first > 5000000000000000
            conn.execute(text('SELECT pg_catalog.setseed(0.25)'))
            conn.execute(text(f"UPDATE \"{trusted}\".visits SET confirmation_token='synthetic-token' WHERE id IN (1,2)"))
            conn.execute(text(f"INSERT INTO \"{trusted}\".visit_services (id,visit_id,service_id,qty,price) VALUES (30,1,11,1,1)"))
            assert conn.execute(text(f'SELECT confirmation_context_epoch FROM "{trusted}".visits WHERE id=1')).scalar_one() > first
            assert conn.execute(text(f'SELECT confirmation_token FROM "{trusted}".visits WHERE id=1')).scalar_one() is None
            assert conn.execute(text(f'SELECT confirmation_token FROM "{trusted}".visits WHERE id=2')).scalar_one() == "synthetic-token"
            conn.execute(text(f"UPDATE \"{trusted}\".patients SET phone='changed' WHERE id=1"))
            assert conn.execute(text(f'SELECT confirmation_token FROM "{trusted}".visits WHERE id=2')).scalar_one() is None
            # Downgrade intentionally keeps the safe function bodies.
            migration.downgrade()
            conn.execute(text(f"UPDATE \"{trusted}\".visits SET confirmation_token='later' WHERE id=2"))
            conn.execute(text(f"UPDATE \"{trusted}\".patients SET phone='changed-again' WHERE id=1"))
            assert conn.execute(text(f'SELECT confirmation_token FROM "{trusted}".visits WHERE id=2')).scalar_one() is None
            conn.execute(text("RESET ROLE"))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(trusted, cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()


def test_offline_requires_explicit_trusted_schema():
    output = io.StringIO()
    ctx = MigrationContext.configure(url="postgresql://", opts={"as_sql": True, "output_buffer": output, "version_table_schema": 'synthetic "schema'})
    migration = _migration("0115_confirmation_trigger_path.py")
    migration.op = Operations(ctx)
    migration.upgrade()
    sql = output.getvalue()
    assert '"synthetic ""schema".invalidate_visit_service_confirmation' in sql
    assert "SET search_path = pg_catalog" in sql and "%I.visits" in sql


@pytest.mark.parametrize("recursive", [0, 1])
def test_sqlite_preserves_tokens_and_retains_allocator(recursive):
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"PRAGMA recursive_triggers={recursive}")
            _create_table(conn)
            old = _old_migration()
            old.op = Operations(MigrationContext.configure(conn))
            old.upgrade()
            conn.execute(text("UPDATE visits SET confirmation_context_epoch=5000000000000000 WHERE id=1"))
            conn.execute(text("UPDATE visits SET confirmation_token='live' WHERE id=1"))
            before = conn.execute(text("SELECT confirmation_context_epoch,confirmation_token FROM visits WHERE id=1")).one()
            migration = _migration("0115_confirmation_trigger_path.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            assert conn.execute(text("SELECT confirmation_context_epoch,confirmation_token FROM visits WHERE id=1")).one() == before
            conn.execute(text("UPDATE visits SET visit_time='13:00' WHERE id=1"))
            first = conn.execute(text("SELECT confirmation_context_epoch FROM visits WHERE id=1")).scalar_one()
            assert first > 5000000000000000
            migration.downgrade()
            migration.upgrade()
            conn.execute(text("UPDATE visits SET visit_time='14:00' WHERE id=1"))
            assert conn.execute(text("SELECT confirmation_context_epoch FROM visits WHERE id=1")).scalar_one() > first
            with pytest.raises(IntegrityError), conn.begin_nested():
                conn.execute(text("UPDATE visits SET confirmation_context_epoch=:v WHERE id=1"), {"v": first})
    finally:
        engine.dispose()


def test_sqlite_exhausted_epoch_refuses_upgrade_without_touching_token():
    engine = create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            _create_table(conn)
            old = _old_migration()
            old.op = Operations(MigrationContext.configure(conn))
            old.upgrade()
            conn.execute(text("UPDATE visits SET confirmation_context_epoch=9223372036854775807, confirmation_token='live' WHERE id=1"))
            migration = _migration("0115_confirmation_trigger_path.py")
            migration.op = Operations(MigrationContext.configure(conn))
            with pytest.raises(IntegrityError), conn.begin_nested():
                migration.upgrade()
            assert conn.execute(text("SELECT confirmation_context_epoch,confirmation_token FROM visits WHERE id=1")).one() == (9223372036854775807, "live")
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgres_exhausted_epoch_refuses_upgrade_without_touching_token():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    schema = "confirm_exhausted_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with engine.begin() as conn:
            _setup_0103(conn)
            conn.execute(text("ALTER TABLE visits DISABLE TRIGGER trg_visit_confirmation_context"))
            conn.execute(text("UPDATE visits SET confirmation_context_epoch=9223372036854775807, confirmation_token='live' WHERE id=1"))
            conn.execute(text("ALTER TABLE visits ENABLE TRIGGER trg_visit_confirmation_context"))
            migration = _migration("0115_confirmation_trigger_path.py")
            migration.op = Operations(MigrationContext.configure(conn))
            with pytest.raises(DBAPIError), conn.begin_nested():
                migration.upgrade()
            assert conn.execute(text("SELECT confirmation_context_epoch,confirmation_token FROM visits WHERE id=1")).one() == (9223372036854775807, "live")
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()

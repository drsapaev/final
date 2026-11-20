"""Birth-date generation and unknown legacy provenance on disposable DBs."""

import importlib.util
import io
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0110_patient_birth_precision.py"
    spec = importlib.util.spec_from_file_location("test_migration_0110", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exercise(conn):
    conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, birth_date DATE, phone TEXT, user_id INTEGER)"))
    conn.execute(text("INSERT INTO patients VALUES (1,'2000-01-01','synthetic',1), (2,'2000-06-03',NULL,NULL)"))
    migration = _migration()
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    first = conn.execute(text("SELECT * FROM patients WHERE id=1")).mappings().one()
    second = conn.execute(text("SELECT * FROM patients WHERE id=2")).mappings().one()
    assert first["birth_date_precision"] == second["birth_date_precision"] == "unknown"
    assert first["birth_date_generation"] > 0 and second["birth_date_generation"] > 0
    original = first["birth_date_generation"]
    trial = conn.begin_nested()
    conn.execute(text("""
        INSERT INTO patient_birth_date_evidence
          (patient_id,patient_id_snapshot,birth_date_generation,actor_user_id_snapshot,actor_role)
        VALUES (1,1,:generation,10,'Admin')
    """), {"generation": original})
    if conn.dialect.name == "postgresql":
        assert conn.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid='patient_birth_date_evidence'::regclass")).scalar_one()
        conn.execute(text("SET LOCAL ROLE pg_read_all_data"))
        assert conn.execute(text("SELECT count(*) FROM patient_birth_date_evidence")).scalar_one() == 0
        conn.execute(text("RESET ROLE"))
    conn.execute(text("UPDATE patients SET birth_date_precision='year_only' WHERE id=1"))
    after_precision = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
    assert after_precision > original
    assert conn.execute(text("SELECT birth_date_generation FROM patient_birth_date_evidence WHERE patient_id=1")).scalar_one() != after_precision
    conn.execute(text("UPDATE patients SET birth_date='2000-02-01' WHERE id=1"))
    changed = conn.execute(text("SELECT birth_date_generation,birth_date_precision FROM patients WHERE id=1")).one()
    assert changed[0] > after_precision and changed[1] == "unknown"
    conn.execute(text("UPDATE patients SET birth_date='2000-01-01' WHERE id=1"))
    restored = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
    assert restored > changed[0]
    assert conn.execute(text("SELECT birth_date_generation FROM patient_birth_date_evidence WHERE patient_id=1")).scalar_one() != restored
    conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
    rebound = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
    conn.execute(text("UPDATE patients SET user_id=1 WHERE id=1"))
    restored_owner = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
    assert restored < rebound < restored_owner
    if conn.dialect.name == "sqlite":
        nested = conn.begin_nested()
        try:
            with pytest.raises(DBAPIError):
                conn.execute(text("UPDATE patients SET birth_date_generation=:old WHERE id=1"), {"old": original})
        finally:
            nested.rollback()
    else:
        conn.execute(text("UPDATE patients SET birth_date_generation=:old WHERE id=1"), {"old": original})
    assert conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one() == restored_owner
    for statement in (
        "UPDATE patient_birth_date_evidence SET actor_role='Doctor' WHERE patient_id=1",
        "DELETE FROM patient_birth_date_evidence WHERE patient_id=1",
    ):
        nested = conn.begin_nested()
        try:
            with pytest.raises(DBAPIError):
                conn.execute(text(statement))
        finally:
            nested.rollback()
    with conn.begin_nested() as nested:
        with pytest.raises(DBAPIError):
            conn.execute(text("UPDATE patients SET birth_date_precision='verified' WHERE id=1"))
        nested.rollback()
    with conn.begin_nested() as nested:
        with pytest.raises(DBAPIError):
            migration.downgrade()
        nested.rollback()
    conn.execute(text("DELETE FROM patients WHERE id=1"))
    evidence = conn.execute(text("SELECT patient_id,patient_id_snapshot FROM patient_birth_date_evidence")).one()
    assert evidence == (None, 1)
    with conn.begin_nested() as nested:
        with pytest.raises(DBAPIError):
            migration.downgrade()
        nested.rollback()
    trial.rollback()
    # A review token is external to this table. Reusing an id must not revive
    # its old generation, even across downgrade and re-upgrade.
    conn.execute(text("DELETE FROM patients WHERE id=1"))
    migration.downgrade()
    assert "birth_date_generation" not in conn.execute(text("SELECT * FROM patients")).keys()
    conn.execute(text("INSERT INTO patients (id,birth_date,user_id) VALUES (1,'2000-01-01',1)"))
    migration.upgrade()
    reused = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
    assert reused > original
    migration.downgrade()


def test_sqlite_legacy_aba_and_safe_downgrade():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    try:
        with engine.begin() as conn:
            _exercise(conn)
    finally:
        engine.dispose()


def test_sqlite_recursive_triggers_preserve_monotonic_fence():
    engine = create_engine("sqlite://")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA recursive_triggers=ON")
    event.listen(engine, "connect", configure)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, birth_date DATE, user_id INTEGER)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            conn.execute(text("INSERT INTO patients (id,birth_date) VALUES (1,'2000-01-01')"))
            conn.execute(text("UPDATE patients SET birth_date_precision='year_only' WHERE id=1"))
            before = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
            conn.execute(text("UPDATE patients SET birth_date='2000-02-01' WHERE id=1"))
            changed = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
            conn.execute(text("UPDATE patients SET birth_date='2000-01-01' WHERE id=1"))
            restored = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
            assert 0 < before < changed < restored
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgres_legacy_aba_and_safe_downgrade():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires disposable clinic_test database")
    schema = "test_birth_precision_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000"})
    try:
        with engine.begin() as conn:
            _exercise(conn)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.mark.integration
@pytest.mark.parametrize("first", ["review", "date_change"])
def test_postgres_date_edit_serializes_with_locked_review(first):
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires disposable clinic_test database")
    schema = "test_birth_race_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"})
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, birth_date DATE, user_id INTEGER)"))
            conn.execute(text("INSERT INTO patients (id,birth_date) VALUES (1, '2000-01-01')"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
        started, pids = threading.Event(), []

        def change_or_review():
            with engine.begin() as conn:
                pids.append(conn.execute(text("SELECT pg_backend_pid() ")).scalar_one())
                started.set()
                if first == "review":
                    conn.execute(text("UPDATE patients SET birth_date='2000-02-01' WHERE id=1"))
                    return None
                return conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1 FOR UPDATE")).scalar_one()

        with engine.connect() as holder:
            transaction = holder.begin()
            original = holder.execute(text("SELECT birth_date_generation FROM patients WHERE id=1 FOR UPDATE")).scalar_one()
            if first == "review":
                holder.execute(text("""
                    INSERT INTO patient_birth_date_evidence
                    (patient_id,patient_id_snapshot,birth_date_generation,actor_user_id_snapshot,actor_role)
                    VALUES (1,1,:generation,10,'Admin')
                """), {"generation": original})
            else:
                holder.execute(text("UPDATE patients SET birth_date='2000-02-01' WHERE id=1"))
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(change_or_review)
                try:
                    assert started.wait(5)
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        assert not future.done()
                        with engine.connect() as observer:
                            if observer.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pids[0]}).scalar_one():
                                break
                        time.sleep(0.02)
                    else:
                        pytest.fail("operation did not wait on patient row")
                finally:
                    transaction.commit()
                observed = future.result(timeout=12)
        with engine.connect() as conn:
            current = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
            assert current != original
            if first == "review":
                assert conn.execute(text("SELECT birth_date_generation FROM patient_birth_date_evidence")).scalar_one() != current
            else:
                assert observed == current
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.mark.integration
def test_postgres_runtime_sequence_requires_minimal_usage():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex
    schema, shadow, role = "test_birth_acl_" + suffix, "test_birth_shadow_" + suffix, "test_birth_role_" + suffix
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"})
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, birth_date DATE, user_id INTEGER)"))
            migration = _migration()
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            conn.execute(text(f'GRANT USAGE, CREATE ON SCHEMA "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT SELECT, INSERT, UPDATE ON patients TO "{role}"'))
            conn.execute(text(f'CREATE SEQUENCE "{shadow}".patient_birth_generation_seq START 1'))
            conn.execute(text(f'GRANT USAGE ON SEQUENCE "{shadow}".patient_birth_generation_seq TO "{role}"'))
            conn.execute(text(f'CREATE FUNCTION "{shadow}".nextval(regclass) RETURNS bigint LANGUAGE sql AS $$ SELECT 1::bigint $$'))
            nested = conn.begin_nested()
            try:
                conn.execute(text(f'SET LOCAL ROLE "{role}"'))
                with pytest.raises(DBAPIError):
                    conn.execute(text("INSERT INTO patients (id,birth_date) VALUES (1,'2000-01-01')"))
            finally:
                nested.rollback()
            conn.execute(text(f'GRANT USAGE ON SEQUENCE patient_birth_generation_seq TO "{role}"'))
            conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            conn.execute(text("INSERT INTO patients (id,birth_date) VALUES (1,'2000-01-01')"))
            before = conn.execute(text("SELECT birth_date_generation FROM patients WHERE id=1")).scalar_one()
            conn.execute(text(f'SET LOCAL search_path TO "{shadow}", "{schema}", pg_catalog'))
            conn.execute(text(f"UPDATE \"{schema}\".patients SET birth_date='2000-02-01' WHERE id=1"))
            assert conn.execute(text(f'SELECT birth_date_generation FROM "{schema}".patients WHERE id=1')).scalar_one() > before
            nested = conn.begin_nested()
            try:
                with pytest.raises(DBAPIError):
                    conn.execute(text(f"SELECT pg_catalog.setval('{schema}.patient_birth_generation_seq'::regclass, 1)"))
            finally:
                nested.rollback()
            conn.execute(text("RESET ROLE"))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(schema, cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
def test_offline_sql_includes_loss_guard(dialect):
    output = io.StringIO()
    ctx = MigrationContext.configure(url=f"{dialect}://", opts={"as_sql": True, "output_buffer": output})
    migration = _migration()
    migration.op = Operations(ctx)
    migration.upgrade()
    migration.downgrade()
    assert "birth_date_generation" in output.getvalue()
    assert "birth_precision_downgrade_guard" in output.getvalue() or "would discard evidence" in output.getvalue()

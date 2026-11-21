"""0108 migration against isolated synthetic SQLite and PostgreSQL schemas."""

import importlib.util
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema


def _migration(conn):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0108_benefit_quota_anchor.py"
    spec = importlib.util.spec_from_file_location("test_0108_benefit_quota_anchor", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn))
    return module


@pytest.fixture(params=["sqlite", "postgresql"])
def schema_connection(request):
    schema = None
    if request.param == "sqlite":
        engine = create_engine("sqlite:///:memory:")
    else:
        raw = os.environ.get("DATABASE_URL", "")
        if not raw or make_url(raw).get_backend_name() != "postgresql":
            if os.environ.get("CI"):
                pytest.fail("CI requires synthetic PostgreSQL DATABASE_URL")
            pytest.skip("requires synthetic PostgreSQL DATABASE_URL")
        engine = create_engine(raw)
        schema = "benefit_0108_" + uuid.uuid4().hex
        with engine.begin() as conn:
            conn.execute(CreateSchema(schema))
    try:
        with engine.connect() as conn:
            if schema:
                conn.execute(text(f'SET search_path TO "{schema}"'))
            conn.execute(text("CREATE TABLE encounter_benefit_applications (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE encounter_benefit_allocations (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE encounter_benefit_events (id INTEGER PRIMARY KEY)"))
            conn.commit()
            yield conn
    finally:
        if schema:
            with engine.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
        engine.dispose()


def test_upgrade_and_empty_downgrade(schema_connection):
    conn = schema_connection
    migration = _migration(conn)
    migration.upgrade()
    columns = {row["name"]: row for row in inspect(conn).get_columns("encounter_benefit_applications")}
    assert all(not columns[name]["nullable"] for name in ("period_timezone", "period_month", "period_year"))
    assert inspect(conn).has_table("encounter_benefit_quota_anchors")
    if conn.dialect.name == "postgresql":
        assert conn.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid = 'encounter_benefit_quota_anchors'::regclass")).scalar_one()
    migration.downgrade()
    assert not inspect(conn).has_table("encounter_benefit_quota_anchors")
    assert {row["name"] for row in inspect(conn).get_columns("encounter_benefit_applications")} == {"id"}
    migration.upgrade()
    assert inspect(conn).has_table("encounter_benefit_quota_anchors")


@pytest.mark.parametrize("table", [
    "encounter_benefit_applications",
    "encounter_benefit_allocations",
    "encounter_benefit_events",
])
def test_upgrade_refuses_existing_evidence(schema_connection, table):
    conn = schema_connection
    conn.execute(text(f"INSERT INTO {table} (id) VALUES (1)"))
    conn.commit()
    with pytest.raises(DBAPIError):
        _migration(conn).upgrade()
    conn.rollback()
    assert conn.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 1
    assert not inspect(conn).has_table("encounter_benefit_quota_anchors")


def test_downgrade_refuses_anchor_and_preserves_evidence(schema_connection):
    conn = schema_connection
    migration = _migration(conn)
    migration.upgrade()
    conn.execute(text("INSERT INTO encounter_benefit_quota_anchors (patient_id,benefit_id) VALUES (1,2)"))
    conn.commit()
    with pytest.raises(DBAPIError):
        migration.downgrade()
    conn.rollback()
    assert conn.execute(text("SELECT count(*) FROM encounter_benefit_quota_anchors")).scalar_one() == 1
    assert inspect(conn).has_table("encounter_benefit_quota_anchors")


def test_anchor_rls_hides_rows_from_nonowner(schema_connection):
    conn = schema_connection
    if conn.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-level security")
    _migration(conn).upgrade()
    schema = conn.execute(text("SELECT current_schema() ")).scalar_one()
    conn.execute(text("INSERT INTO encounter_benefit_quota_anchors (patient_id,benefit_id) VALUES (1,2)"))
    conn.execute(text(f'GRANT USAGE ON SCHEMA "{schema}" TO pg_read_all_data'))
    conn.execute(text("SET LOCAL row_security = on"))
    conn.execute(text('SET LOCAL ROLE "pg_read_all_data"'))
    assert conn.execute(text("SELECT count(*) FROM encounter_benefit_quota_anchors")).scalar_one() == 0
    conn.execute(text("RESET ROLE"))


def test_pair_anchor_blocks_competing_budget_consumption_in_postgresql(schema_connection):
    conn = schema_connection
    if conn.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock behavior")
    _migration(conn).upgrade()
    schema = conn.execute(text("SELECT current_schema() ")).scalar_one()
    conn.execute(text("CREATE TABLE quota_test_usage (amount INTEGER NOT NULL)"))
    conn.commit()
    started = threading.Event()
    worker_pid = []

    def consume_later():
        with conn.engine.begin() as other:
            other.execute(text(f'SET search_path TO "{schema}"'))
            other.execute(text("SET LOCAL lock_timeout = '5s'"))
            worker_pid.append(other.execute(text("SELECT pg_backend_pid() ")).scalar_one())
            started.set()
            other.execute(text("""
                INSERT INTO encounter_benefit_quota_anchors (patient_id, benefit_id)
                VALUES (1, 2) ON CONFLICT DO NOTHING
            """))
            other.execute(text("""
                SELECT patient_id FROM encounter_benefit_quota_anchors
                WHERE patient_id=1 AND benefit_id=2 FOR UPDATE
            """))
            used = other.execute(text("SELECT COALESCE(sum(amount), 0) FROM quota_test_usage")).scalar_one()
            amount = min(7, 10 - used)
            other.execute(text("INSERT INTO quota_test_usage (amount) VALUES (:amount)"), {"amount": amount})
            return amount

    with conn.begin():
        conn.execute(text("INSERT INTO encounter_benefit_quota_anchors (patient_id, benefit_id) VALUES (1, 2)"))
        conn.execute(text("INSERT INTO quota_test_usage (amount) VALUES (7)"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(consume_later)
            assert started.wait(5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                blocked = conn.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": worker_pid[0]}).scalar_one()
                if blocked:
                    break
                time.sleep(0.02)
            else:
                pytest.fail("competing quota transaction did not wait on the anchor")
            conn.commit()
            assert future.result(timeout=5) == 3
    assert conn.execute(text("SELECT sum(amount) FROM quota_test_usage")).scalar_one() == 10

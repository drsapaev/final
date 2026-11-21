"""The 0105 schema preserves unknown legacy bindings and audited history."""

import importlib.util
import io
import os
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema


def _migration():
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0105_price_override_binding.py"
    spec = importlib.util.spec_from_file_location("test_migration_0105", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _exercise(conn):
    conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    conn.execute(text("CREATE TABLE visit_services (id INTEGER PRIMARY KEY)"))
    conn.execute(text("CREATE TABLE doctor_price_overrides (id INTEGER PRIMARY KEY, status VARCHAR(32))"))
    conn.execute(text("INSERT INTO users VALUES (1)"))
    conn.execute(text("INSERT INTO visit_services VALUES (2)"))
    conn.execute(text("INSERT INTO doctor_price_overrides VALUES (10, 'pending')"))
    migration = _migration()
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    row = conn.execute(text("SELECT * FROM doctor_price_overrides WHERE id=10")).mappings().one()
    for key in ("target_scope", "target_visit_service_id", "visit_context_epoch", "doctor_owner_user_id", "doctor_owner_generation"):
        assert row[key] is None
    conn.execute(text("""
        UPDATE doctor_price_overrides SET target_scope='visit_service', target_visit_service_id=2,
          visit_context_epoch=3, doctor_owner_user_id=1, doctor_owner_generation=4 WHERE id=10
    """))
    with conn.begin_nested() as nested:
        with pytest.raises(DBAPIError):
            migration.downgrade()
        nested.rollback()
    assert conn.execute(text("SELECT target_scope FROM doctor_price_overrides WHERE id=10")).scalar_one() == "visit_service"
    conn.execute(text("DELETE FROM visit_services WHERE id=2"))
    conn.execute(text("DELETE FROM users WHERE id=1"))
    row = conn.execute(text("SELECT * FROM doctor_price_overrides WHERE id=10")).mappings().one()
    assert row["target_visit_service_id"] is None
    assert row["doctor_owner_user_id"] is None
    assert row["target_scope"] == "visit_service"
    # Even orphaned requests retain context and block a lossy downgrade.
    with conn.begin_nested() as nested:
        with pytest.raises(DBAPIError):
            migration.downgrade()
        nested.rollback()
    conn.execute(text("DELETE FROM doctor_price_overrides WHERE id=10"))
    migration.downgrade()
    assert "target_scope" not in conn.execute(text("SELECT * FROM doctor_price_overrides")).keys()


def test_sqlite_binding_upgrade_and_downgrade():
    engine = create_engine("sqlite://")
    event.listen(engine, "connect", lambda connection, _: connection.execute("PRAGMA foreign_keys=ON"))
    try:
        with engine.begin() as conn:
            _exercise(conn)
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgresql_binding_upgrade_and_downgrade():
    raw = os.environ.get("DATABASE_URL", "").strip()
    ci = os.environ.get("CI", "").lower() == "true"
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_override_" + uuid.uuid4().hex
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


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
def test_offline_sql_has_fail_closed_downgrade_guard(dialect):
    output = io.StringIO()
    context = MigrationContext.configure(url=f"{dialect}://", opts={"as_sql": True, "output_buffer": output})
    migration = _migration()
    migration.op = Operations(context)
    migration.upgrade()
    migration.downgrade()
    sql = output.getvalue().lower()
    assert "target_visit_service_id" in sql
    assert "price_override_downgrade_guard" in sql or "would discard bound requests" in sql

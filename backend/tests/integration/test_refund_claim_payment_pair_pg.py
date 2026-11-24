"""Protect payment-to-request binding in the PostgreSQL refund ledger."""

from contextlib import contextmanager
from os import getenv
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.dialects import postgresql, sqlite
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, CreateTable, DropSchema

from app.models.refund_deposit import PaymentRefundClaim
from tests._pg_admin_guard import is_local_admin_dsn
from tests.integration.test_encounter_migration_pg import _migration

_VERSION = "0151_refund_claim_payment_pair.py"
_GUARD_VERSION = "0152_refund_claim_truncate_guard.py"
_CONSTRAINT = "fk_payment_refund_claims_request_payment"
_INDEX = "uq_refund_requests_id_payment"


@contextmanager
def _transaction(engine, schema):
    with engine.begin() as conn:
        quoted = conn.dialect.identifier_preparer.quote_schema(schema)
        conn.exec_driver_sql(f"SET LOCAL search_path TO {quoted}, pg_catalog")
        yield conn


@pytest.fixture
def refund_schema():
    dsn = getenv("DATABASE_URL", "")
    if not is_local_admin_dsn(dsn):
        pytest.skip("requires a disposable local PostgreSQL database")
    url = make_url(dsn)
    if url.query or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires a disposable local clinic_test database")

    engine = create_engine(url, hide_parameters=True)
    schema = f"refund_claim_pair_{uuid4().hex}"
    try:
        with engine.begin() as conn:
            assert conn.scalar(text("SELECT pg_catalog.current_database()")) == url.database
            conn.execute(CreateSchema(schema))
        with _transaction(engine, schema) as conn:
            conn.exec_driver_sql("CREATE TABLE payments (id integer PRIMARY KEY)")
            conn.exec_driver_sql("""
                CREATE TABLE refund_requests (
                    id integer PRIMARY KEY,
                    payment_id integer NOT NULL REFERENCES payments(id) ON DELETE RESTRICT
                )
            """)
            conn.exec_driver_sql("""
                CREATE TABLE payment_refund_claims (
                    id integer PRIMARY KEY,
                    payment_id integer NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
                    refund_request_id integer REFERENCES refund_requests(id) ON DELETE SET NULL
                )
            """)
            conn.exec_driver_sql("""
                CREATE UNIQUE INDEX uq_payment_refund_claims_payment
                    ON payment_refund_claims (payment_id)
            """)
            conn.exec_driver_sql("ALTER TABLE payment_refund_claims ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql("INSERT INTO payments (id) VALUES (1), (2), (3)")
            conn.exec_driver_sql("INSERT INTO refund_requests (id, payment_id) VALUES (1, 1), (2, 2)")
        yield engine, schema
    finally:
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()


def _migrate(conn, schema, *, downgrade=False, version=_VERSION):
    migration = _migration(version)
    operations = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
    migration.op = operations
    if downgrade:
        migration.downgrade()
    else:
        migration.upgrade()


def _constraint(conn, name):
    return conn.execute(text("""
        SELECT convalidated, condeferrable, condeferred
        FROM pg_catalog.pg_constraint
        WHERE conrelid = 'payment_refund_claims'::regclass AND conname = :name
    """), {"name": name}).one_or_none()


def test_model_uses_postgres_pair_and_preserves_sqlite_foreign_key():
    table = PaymentRefundClaim.__table__
    postgres_ddl = str(CreateTable(table).compile(dialect=postgresql.dialect()))
    sqlite_ddl = str(CreateTable(table).compile(dialect=sqlite.dialect()))
    pair = "FOREIGN KEY(refund_request_id, payment_id) REFERENCES refund_requests (id, payment_id)"
    original = "FOREIGN KEY(refund_request_id) REFERENCES refund_requests (id) ON DELETE SET NULL"
    assert pair in postgres_ddl and "DEFERRABLE INITIALLY DEFERRED" in postgres_ddl
    assert original in postgres_ddl and original in sqlite_ddl
    assert pair not in sqlite_ddl
    relation = inspect(PaymentRefundClaim).relationships["refund_request"]
    assert relation.local_columns == {table.c.refund_request_id}


def test_matching_pairs_work_with_narrow_runtime_privileges(refund_schema):
    engine, schema = refund_schema
    role = f"refund_claim_writer_{uuid4().hex}"
    quoted_role = engine.dialect.identifier_preparer.quote(role)
    quoted_schema = engine.dialect.identifier_preparer.quote_schema(schema)
    try:
        with _transaction(engine, schema) as conn:
            _migrate(conn, schema)
            assert _constraint(conn, _CONSTRAINT) == (True, True, True)
            conn.exec_driver_sql(f"CREATE ROLE {quoted_role} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA {quoted_schema} TO {quoted_role}")
            conn.exec_driver_sql(f"GRANT INSERT ON payment_refund_claims TO {quoted_role}")
            conn.exec_driver_sql(f"""
                CREATE POLICY synthetic_claim_writer ON payment_refund_claims
                FOR INSERT TO {quoted_role} WITH CHECK (true)
            """)
        with _transaction(engine, schema) as conn:
            conn.exec_driver_sql(f"SET LOCAL ROLE {quoted_role}")
            assert conn.scalar(text("SELECT pg_catalog.row_security_active('payment_refund_claims')"))
            assert not conn.scalar(text(
                "SELECT pg_catalog.has_table_privilege(CURRENT_USER, 'refund_requests', 'SELECT')"
            ))
            conn.exec_driver_sql("""
                INSERT INTO payment_refund_claims (id, payment_id, refund_request_id)
                VALUES (1, 1, 1), (3, 3, NULL)
            """)
        with pytest.raises(DBAPIError) as raised, _transaction(engine, schema) as conn:
            conn.exec_driver_sql(f"SET LOCAL ROLE {quoted_role}")
            conn.exec_driver_sql("""
                INSERT INTO payment_refund_claims (id, payment_id, refund_request_id)
                VALUES (2, 2, 1)
            """)
        assert raised.value.orig.sqlstate == "23503"
        assert raised.value.orig.diag.constraint_name == _CONSTRAINT
        with _transaction(engine, schema) as conn:
            assert conn.exec_driver_sql(
                "SELECT id, payment_id, refund_request_id FROM payment_refund_claims ORDER BY id"
            ).all() == [(1, 1, 1), (3, 3, None)]
    finally:
        with _transaction(engine, schema) as conn:
            conn.exec_driver_sql("DROP POLICY IF EXISTS synthetic_claim_writer ON payment_refund_claims")
            if conn.scalar(text("SELECT 1 FROM pg_catalog.pg_roles WHERE rolname = :role"), {"role": role}):
                conn.exec_driver_sql(f"DROP OWNED BY {quoted_role}")
                conn.exec_driver_sql(f"DROP ROLE {quoted_role}")


def test_parent_changes_preserve_payment_and_allow_legacy_unlink(refund_schema):
    engine, schema = refund_schema
    with _transaction(engine, schema) as conn:
        _migrate(conn, schema)
        conn.exec_driver_sql("""
            INSERT INTO payment_refund_claims (id, payment_id, refund_request_id) VALUES (1, 1, 1)
        """)
    with pytest.raises(DBAPIError) as raised, _transaction(engine, schema) as conn:
        conn.exec_driver_sql("UPDATE refund_requests SET payment_id = 2 WHERE id = 1")
    assert raised.value.orig.diag.constraint_name == _CONSTRAINT
    with _transaction(engine, schema) as conn:
        assert conn.scalar(text("SELECT payment_id FROM refund_requests WHERE id = 1")) == 1
        conn.exec_driver_sql("DELETE FROM refund_requests WHERE id = 1")
    with _transaction(engine, schema) as conn:
        assert conn.exec_driver_sql(
            "SELECT payment_id, refund_request_id FROM payment_refund_claims WHERE id = 1"
        ).one() == (1, None)
        _migrate(conn, schema, downgrade=True)
        assert _constraint(conn, _CONSTRAINT) is None
        assert _constraint(conn, "payment_refund_claims_refund_request_id_fkey") == (True, False, False)
        assert conn.scalar(text("SELECT pg_catalog.to_regclass(:name)"), {"name": _INDEX}) is None


def test_legacy_mismatch_rolls_back_migration_and_preserves_rows(refund_schema):
    engine, schema = refund_schema
    with _transaction(engine, schema) as conn:
        conn.exec_driver_sql("""
            INSERT INTO payment_refund_claims (id, payment_id, refund_request_id) VALUES (1, 2, 1)
        """)
    with pytest.raises(DBAPIError) as raised, _transaction(engine, schema) as conn:
        _migrate(conn, schema)
    assert raised.value.orig.sqlstate == "23503"
    assert raised.value.orig.diag.message_primary == "Refund claims require payment reconciliation"
    assert raised.value.orig.diag.message_detail is None
    with _transaction(engine, schema) as conn:
        assert _constraint(conn, _CONSTRAINT) is None
        assert conn.scalar(text("SELECT pg_catalog.to_regclass(:name)"), {"name": _INDEX}) is None
        assert conn.exec_driver_sql(
            "SELECT id, payment_id, refund_request_id FROM payment_refund_claims"
        ).all() == [(1, 2, 1)]


def test_migration_preserves_operator_timeout_and_rolls_back_contention(refund_schema):
    engine, schema = refund_schema
    with _transaction(engine, schema) as blocker:
        blocker.exec_driver_sql("LOCK TABLE refund_requests IN ROW EXCLUSIVE MODE")
        with pytest.raises(DBAPIError) as raised, _transaction(engine, schema) as conn:
            conn.exec_driver_sql("SET LOCAL lock_timeout = '50ms'")
            _migrate(conn, schema)
        assert raised.value.orig.sqlstate == "55P03"
    with _transaction(engine, schema) as conn:
        assert _constraint(conn, _CONSTRAINT) is None
        conn.exec_driver_sql("SET LOCAL lock_timeout = '50ms'")
        _migrate(conn, schema)
        assert conn.scalar(text("SHOW lock_timeout")) == "50ms"
        assert _constraint(conn, _CONSTRAINT) == (True, True, True)


def _assert_truncate_guard(conn, statement):
    with pytest.raises(DBAPIError) as rejected, conn.begin_nested():
        conn.exec_driver_sql(statement)
    error = rejected.value.orig
    assert error.sqlstate == "23514"
    assert error.diag.message_primary == "refund reservations cannot be truncated"


def test_refund_claim_guard_preserves_rows_during_bulk_cleanup(refund_schema):
    engine, schema = refund_schema
    role = f"synthetic_claim_cleanup_{uuid4().hex}"
    quote = engine.dialect.identifier_preparer.quote
    with _transaction(engine, schema) as conn, conn.begin_nested() as setup:
        _migrate(conn, schema)
        _migrate(conn, schema, version=_GUARD_VERSION)
        # Check the deferred FK before exercising the statement trigger.
        conn.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
        conn.exec_driver_sql("CREATE TABLE synthetic_refund_cache (id integer)")
        conn.exec_driver_sql("INSERT INTO synthetic_refund_cache VALUES (1)")
        conn.exec_driver_sql("""
            INSERT INTO payment_refund_claims (id, payment_id, refund_request_id) VALUES (1, 1, 1)
        """)
        conn.exec_driver_sql(f"CREATE ROLE {quote(role)} NOLOGIN NOSUPERUSER NOBYPASSRLS")
        conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA {quote(schema)} TO {quote(role)}")
        conn.exec_driver_sql(f"GRANT TRUNCATE ON synthetic_refund_cache, payment_refund_claims TO {quote(role)}")
        conn.exec_driver_sql(f"SET LOCAL ROLE {quote(role)}")
        try:
            assert conn.scalar(text("SELECT pg_catalog.row_security_active('payment_refund_claims')"))
            assert not conn.scalar(text(
                "SELECT pg_catalog.has_function_privilege('prevent_refund_claim_truncate()', 'EXECUTE')"
            ))
            _assert_truncate_guard(conn, "TRUNCATE synthetic_refund_cache, payment_refund_claims")
        finally:
            conn.exec_driver_sql("RESET ROLE")
        assert conn.scalar(text("SELECT id FROM synthetic_refund_cache")) == 1
        assert conn.execute(text(
            "SELECT payment_id, refund_request_id FROM payment_refund_claims"
        )).one() == (1, 1)
        setup.rollback()


def test_refund_claim_guard_is_enabled_in_replica_mode(refund_schema):
    engine, schema = refund_schema
    with _transaction(engine, schema) as conn:
        if not conn.scalar(text("SELECT rolsuper FROM pg_catalog.pg_roles WHERE rolname=CURRENT_USER")):
            pytest.skip("requires the disposable PostgreSQL bootstrap role for replica mode")
        _migrate(conn, schema)
        _migrate(conn, schema, version=_GUARD_VERSION)
        conn.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
        conn.exec_driver_sql("""
            INSERT INTO payment_refund_claims (id, payment_id, refund_request_id) VALUES (1, 1, 1)
        """)
        conn.exec_driver_sql("SET LOCAL session_replication_role = 'replica'")
        _assert_truncate_guard(conn, "TRUNCATE payment_refund_claims")
        conn.exec_driver_sql("SET LOCAL session_replication_role = 'origin'")
        assert conn.scalar(text("SELECT payment_id FROM payment_refund_claims")) == 1


def test_refund_claim_guard_preserves_row_release_and_upgrade_roundtrip(refund_schema):
    engine, schema = refund_schema
    with _transaction(engine, schema) as conn:
        _migrate(conn, schema)
        _migrate(conn, schema, version=_GUARD_VERSION)
        conn.exec_driver_sql("SET CONSTRAINTS ALL IMMEDIATE")
        conn.exec_driver_sql("""
            INSERT INTO payment_refund_claims (id, payment_id, refund_request_id) VALUES (1, 1, 1)
        """)
        released = conn.exec_driver_sql("""
            DELETE FROM payment_refund_claims
            WHERE id = 1 AND payment_id = 1 AND refund_request_id = 1
            RETURNING id
        """).scalar_one()
        assert released == 1
        conn.exec_driver_sql("""
            INSERT INTO payment_refund_claims (id, payment_id, refund_request_id) VALUES (2, 1, 1)
        """)
        _migrate(conn, schema, downgrade=True, version=_GUARD_VERSION)
        assert conn.scalar(text("SELECT pg_catalog.to_regprocedure('prevent_refund_claim_truncate()')")) is None
        assert _constraint(conn, _CONSTRAINT) == (True, True, True)
        _migrate(conn, schema, version=_GUARD_VERSION)
        _assert_truncate_guard(conn, "TRUNCATE payment_refund_claims")
        assert conn.execute(text(
            "SELECT id, payment_id, refund_request_id FROM payment_refund_claims"
        )).one() == (2, 1, 1)


def test_refund_claim_guard_leaves_sqlite_claims_intact():
    engine = create_engine("sqlite://")
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql("CREATE TABLE payment_refund_claims (id integer PRIMARY KEY)")
            conn.exec_driver_sql("INSERT INTO payment_refund_claims VALUES (1)")
            _migrate(conn, None, version=_GUARD_VERSION)
            _migrate(conn, None, downgrade=True, version=_GUARD_VERSION)
            assert conn.scalar(text("SELECT id FROM payment_refund_claims")) == 1
    finally:
        engine.dispose()


def test_refund_claim_guard_installation_rolls_back_on_lock_timeout(refund_schema):
    engine, schema = refund_schema
    with _transaction(engine, schema) as conn:
        _migrate(conn, schema)
        conn.exec_driver_sql("""
            INSERT INTO payment_refund_claims (id, payment_id, refund_request_id) VALUES (1, 1, 1)
        """)
    with _transaction(engine, schema) as blocker:
        blocker.exec_driver_sql("LOCK TABLE payment_refund_claims IN ROW EXCLUSIVE MODE")
        with pytest.raises(DBAPIError) as raised, _transaction(engine, schema) as conn:
            conn.exec_driver_sql("SET LOCAL lock_timeout = '50ms'")
            _migrate(conn, schema, version=_GUARD_VERSION)
        assert raised.value.orig.sqlstate == "55P03"
    with _transaction(engine, schema) as conn:
        assert conn.scalar(text("SELECT pg_catalog.to_regprocedure('prevent_refund_claim_truncate()')")) is None
        assert conn.scalar(text("SELECT payment_id FROM payment_refund_claims")) == 1
        _migrate(conn, schema, version=_GUARD_VERSION)
        assert conn.scalar(text("""
            SELECT tgenabled FROM pg_catalog.pg_trigger
            WHERE tgrelid='payment_refund_claims'::regclass AND tgname='payment_refund_claims_no_truncate'
        """)) == "A"

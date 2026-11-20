"""Real 0134 constraints on synthetic registrar-cart invoice identities."""

from __future__ import annotations

import os
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import DropSchema

from tests.integration.test_encounter_migration_pg import _migration

pytestmark = pytest.mark.integration
_ORIGIN = "registrar_encounter_id_snapshot"
_GENERATION = "registrar_encounter_generation_snapshot"
_IMMUTABLE = "registrar cart origin is immutable"
_MISMATCH = "registrar cart invoice membership does not match its origin"


def _migrate(conn, schema, *, direction="upgrade"):
    migration = _migration("0134_registrar_cart_origin.py")
    migration.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
    getattr(migration, direction)()


def _predecessor(conn):
    for statement in (
        "CREATE TABLE encounters (id INTEGER PRIMARY KEY, patient_id INTEGER, generation BIGINT, provenance TEXT)",
        "CREATE TABLE visits (id INTEGER PRIMARY KEY, patient_id INTEGER, encounter_id INTEGER REFERENCES encounters)",
        "CREATE TABLE payment_invoices (id INTEGER PRIMARY KEY, patient_id INTEGER, total_amount INTEGER NOT NULL)",
        "CREATE TABLE payment_invoice_visits (invoice_id INTEGER NOT NULL REFERENCES payment_invoices, "
        "visit_id INTEGER NOT NULL REFERENCES visits)",
        "INSERT INTO encounters VALUES (10,1,51,'new'), (11,1,52,'new'), (12,2,53,'new')",
        "INSERT INTO visits VALUES (101,1,10),(102,1,10),(110,1,11),(120,2,12)",
        "INSERT INTO payment_invoices VALUES (1,1,200)",
        "INSERT INTO payment_invoice_visits VALUES (1,101),(1,102)",
    ):
        conn.exec_driver_sql(statement)


@pytest.fixture
def origin_db(kind, tmp_path):
    if kind == "sqlite":
        engine = sa.create_engine(f"sqlite:///{tmp_path / 'registrar-origin.sqlite'}")
        try:
            with engine.begin() as conn:
                conn.exec_driver_sql("PRAGMA foreign_keys=ON")
                _predecessor(conn)
                _migrate(conn, None)
            yield engine, None, None
        finally:
            engine.dispose()
        return

    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test PostgreSQL database")
    suffix = uuid4().hex
    schema, owner, runtime = (prefix + suffix for prefix in ("cart_", "owner_", "runtime_"))
    password = "synthetic_" + uuid4().hex
    connect_args = {"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"}
    engine = sa.create_engine(url, connect_args=connect_args, hide_parameters=True)
    client = sa.create_engine(url.set(username=runtime, password=password), connect_args=connect_args, hide_parameters=True)
    try:
        with engine.begin() as conn:
            conn.exec_driver_sql(f"CREATE ROLE {owner} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            conn.exec_driver_sql(f"CREATE ROLE {runtime} LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD '{password}'")
            conn.exec_driver_sql(f"CREATE SCHEMA {schema} AUTHORIZATION {owner}")
            conn.exec_driver_sql(f"SET LOCAL ROLE {owner}")
            _predecessor(conn)
            _migrate(conn, schema)
            conn.exec_driver_sql("ALTER TABLE encounters ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql("ALTER TABLE payment_invoices ENABLE ROW LEVEL SECURITY")
            conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema} TO {runtime}")
            conn.exec_driver_sql(f"GRANT SELECT,INSERT,UPDATE ON payment_invoices TO {runtime}")
            conn.exec_driver_sql(f"GRANT INSERT ON payment_invoice_visits TO {runtime}")
            conn.exec_driver_sql(f"CREATE POLICY synthetic_invoice ON payment_invoices TO {runtime} USING(true) WITH CHECK(true)")
        yield engine, schema, client
    finally:
        client.dispose()
        with engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True, if_exists=True))
            conn.exec_driver_sql(f"DROP ROLE IF EXISTS {runtime}, {owner}")
        engine.dispose()


def _insert_cart_invoice(conn, *, invoice_id=2, patient_id=1, encounter_id=10, generation=51, links=(101, 102)):
    conn.execute(sa.text(f"""
        INSERT INTO payment_invoices (id,patient_id,total_amount,{_ORIGIN},{_GENERATION})
        VALUES (:invoice,:patient,200,:encounter,:generation)
    """), {"invoice": invoice_id, "patient": patient_id, "encounter": encounter_id, "generation": generation})
    if links:
        conn.execute(sa.text("INSERT INTO payment_invoice_visits VALUES (:invoice,:visit)"),
                     [{"invoice": invoice_id, "visit": visit_id} for visit_id in links])


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_origin_is_creation_evidence_and_legacy_invoice_is_unmarked(origin_db):
    engine, schema, client = origin_db
    with engine.begin() as conn:
        _migrate(conn, schema, direction="downgrade")
        _migrate(conn, schema)
        assert tuple(conn.exec_driver_sql(f"SELECT {_ORIGIN},{_GENERATION} FROM payment_invoices WHERE id=1").one()) == (None, None)
        with pytest.raises(DBAPIError, match=_IMMUTABLE), conn.begin_nested():
            conn.exec_driver_sql(f"UPDATE payment_invoices SET {_ORIGIN}=10,{_GENERATION}=51 WHERE id=1")
    with (client or engine).begin() as conn:
        _insert_cart_invoice(conn)
        assert tuple(conn.exec_driver_sql(f"SELECT {_ORIGIN},{_GENERATION} FROM payment_invoices WHERE id=2").one()) == (10, 51)
        conn.exec_driver_sql("UPDATE payment_invoices SET total_amount=150 WHERE id=2")
        for fields in (f"{_ORIGIN}=NULL,{_GENERATION}=NULL", "patient_id=2", "id=40"):
            with pytest.raises(DBAPIError, match=_IMMUTABLE), conn.begin_nested():
                conn.exec_driver_sql(f"UPDATE payment_invoices SET {fields} WHERE id=2")
    with pytest.raises(DBAPIError, match=r"origin prevents downgrade|CHECK constraint failed"), engine.begin() as conn:
        _migrate(conn, schema, direction="downgrade")


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_origin_rejects_wrong_patient_generation_and_duplicate_group(origin_db):
    engine, _, client = origin_db
    target = client or engine
    for fields in ({"patient_id": 2}, {"generation": 50}):
        with pytest.raises(DBAPIError, match=_MISMATCH), target.begin() as conn:
            _insert_cart_invoice(conn, **fields)
    with pytest.raises(DBAPIError, match="ck_payment_invoice_registrar_origin|membership does not match"), target.begin() as conn:
        _insert_cart_invoice(conn, encounter_id=None)
    with target.begin() as conn:
        _insert_cart_invoice(conn)
    with pytest.raises(DBAPIError, match=_IMMUTABLE + "|uq_payment_invoice_registrar_encounter"), target.begin() as conn:
        _insert_cart_invoice(conn, invoice_id=3)


@pytest.mark.parametrize("kind", ["postgresql"])
def test_postgres_rejects_incomplete_mixed_or_duplicate_links_at_commit(origin_db):
    engine, _, client = origin_db
    with client.connect() as conn:
        assert conn.exec_driver_sql("SELECT pg_catalog.has_table_privilege(CURRENT_USER,'encounters','SELECT')").scalar_one() is False
        assert conn.exec_driver_sql("SELECT pg_catalog.has_function_privilege(CURRENT_USER,'protect_registrar_cart_origin()','EXECUTE')").scalar_one() is False
    for links in ((), (101,), (101, 110), (101, 102, 120), (101, 101, 102)):
        with pytest.raises(DBAPIError, match=_MISMATCH), client.begin() as conn:
            _insert_cart_invoice(conn, links=links)
        with engine.connect() as conn:
            assert conn.exec_driver_sql("SELECT count(*) FROM payment_invoices WHERE id=2").scalar_one() == 0
            assert conn.exec_driver_sql("SELECT count(*) FROM payment_invoice_visits WHERE invoice_id=2").scalar_one() == 0

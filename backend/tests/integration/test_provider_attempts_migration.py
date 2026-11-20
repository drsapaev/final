"""Isolated synthetic 0111 schema tests; not a full Alembic chain test."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

_PATH = Path(__file__).resolve().parents[2] / "alembic/versions/0111_provider_attempts.py"
_SPEC = importlib.util.spec_from_file_location("synthetic_provider_attempt_0111", _PATH)
assert _SPEC and _SPEC.loader
_MIGRATION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_MIGRATION)


def _predecessor(connection):
    meta = sa.MetaData()
    users = sa.Table("users", meta, sa.Column("id", sa.Integer, primary_key=True))
    visits = sa.Table("visits", meta, sa.Column("id", sa.Integer, primary_key=True))
    payments = sa.Table("payments", meta, sa.Column("id", sa.Integer, primary_key=True))
    invoices = sa.Table("payment_invoices", meta, sa.Column("id", sa.Integer, primary_key=True))
    meta.create_all(connection)
    for table in (users, visits, payments, invoices):
        connection.execute(table.insert(), [{"id": 1}, {"id": 2}])


def _upgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        _MIGRATION.upgrade()


def _downgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        _MIGRATION.downgrade()


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'attempts.sqlite'}")

    @sa.event.listens_for(engine, "connect")
    def foreign_keys(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    try:
        with engine.begin() as connection:
            _predecessor(connection)
            _upgrade(connection)
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("PROVIDER_ATTEMPT_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    if not os.getenv("CI") and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable clinic_test database")
    schema = "test_provider_attempt_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        with engine.begin() as connection:
            _predecessor(connection)
            _upgrade(connection)
        yield engine, admin, schema
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _engine(kind, request):
    return request.getfixturevalue("sqlite_engine") if kind == "sqlite" else request.getfixturevalue("pg_engine")[0]


def _insert_attempt(connection, ident=10, target=1, *, provider="click", actor=1, key_hash=None):
    connection.execute(sa.text("""
        INSERT INTO provider_attempts
          (id,public_id,target_kind,payment_id,payment_id_snapshot,
           actor_user_id,actor_user_id_snapshot,provider,merchant_hash,order_ref,
           fingerprint,client_key_hash,amount_minor,currency,currency_exponent,status)
        VALUES (:id,:public,'payment',:target,:target,:actor,:actor,:provider,:merchant,:order,
                :fingerprint,:key_hash,'29','UZS',2,'prepared')
    """), {"id": ident, "public": str(uuid4()), "target": target, "provider": provider,
            "merchant": "a" * 64, "order": f"synthetic_{ident}", "fingerprint": "b" * 64,
            "actor": actor, "key_hash": key_hash})


def _insert_history(connection, ident=20, attempt=10, visit=1, amount="29"):
    connection.execute(sa.text("""
        INSERT INTO provider_attempt_visits
          (id,attempt_id,visit_id,visit_id_snapshot,patient_id_snapshot,context_epoch,amount_minor)
        VALUES (:id,:attempt,:visit,:visit,1,11,:amount)
    """), {"id": ident, "attempt": attempt, "visit": visit, "amount": amount})


def _reserve(connection, visit=1, attempt=10, history=20):
    connection.execute(sa.text("""
        INSERT INTO provider_active_visit_reservations (visit_id,attempt_id,attempt_visit_id)
        VALUES (:visit,:attempt,:history)
    """), {"visit": visit, "attempt": attempt, "history": history})


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_client_key_unique_per_actor_and_nullable(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection, key_hash="c" * 64)
        _insert_attempt(connection, ident=11, target=2, actor=2, key_hash="c" * 64)
        _insert_attempt(connection, ident=12, target=1, key_hash=None)
        _insert_attempt(connection, ident=13, target=2, key_hash=None)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _insert_attempt(connection, ident=14, target=2, actor=1, key_hash="c" * 64)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _insert_attempt(connection, ident=15, target=2, actor=1, key_hash="z" * 64)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_one_visit_reservation_across_providers_and_consistent_history(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection)
        _insert_attempt(connection, ident=11, target=2, provider="payme")
        _insert_history(connection)
        _insert_history(connection, ident=21, attempt=11, visit=1, amount="0")
        _insert_history(connection, ident=22, attempt=11, visit=2, amount="1")
        _reserve(connection)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _reserve(connection, visit=1, attempt=11, history=21)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        _reserve(connection, visit=2, attempt=10, history=22)
    with engine.begin() as connection:
        _reserve(connection, visit=2, attempt=11, history=22)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_delete_preserves_live_fk_snapshots_and_active_reservation(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection)
        _insert_history(connection)
        _reserve(connection)
        connection.execute(sa.text("DELETE FROM payments WHERE id=1"))
        connection.execute(sa.text("DELETE FROM users WHERE id=1"))
        row = connection.execute(sa.text("SELECT payment_id,payment_id_snapshot,actor_user_id,actor_user_id_snapshot FROM provider_attempts WHERE id=10")).one()
        assert tuple(row) == (None, 1, None, 1)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM visits WHERE id=1"))
    # DB FK behavior only: direct deletion is NOT an authorized release.
    with engine.begin() as connection:
        connection.execute(sa.text("DELETE FROM provider_active_visit_reservations WHERE visit_id=1"))
        connection.execute(sa.text("DELETE FROM visits WHERE id=1"))
        row = connection.execute(sa.text("SELECT visit_id,visit_id_snapshot,patient_id_snapshot FROM provider_attempt_visits WHERE id=20")).one()
        assert tuple(row) == (None, 1, 1)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("amount", ["", "0", "00", "01", "-1", "+1", "1.0", "NaN", "9" * 129])
def test_noncanonical_or_nonpositive_attempt_amount_rejected(kind, amount, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(sa.text("UPDATE provider_attempts SET amount_minor=:amount WHERE id=10"), {"amount": amount})


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("amount", ["", "00", "01", "-1", "1.0", "9" * 129])
def test_noncanonical_history_amount_rejected(kind, amount, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _insert_history(connection, amount=amount)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("column,value", [
    ("status", "approved"), ("target_kind", "payment_invoice"),
    ("actor_user_id", 2), ("payment_id", 2), ("currency", "uzs"),
    ("currency_exponent", -1), ("merchant_hash", "g" * 64),
])
def test_invalid_attempt_metadata_is_rejected(kind, column, value, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(sa.text(f"UPDATE provider_attempts SET {column}=:value WHERE id=10"), {"value": value})


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_provider_order_is_unique_per_merchant(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection)
        _insert_attempt(connection, ident=11, target=2)
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(sa.text("UPDATE provider_attempts SET order_ref='synthetic_10' WHERE id=11"))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_downgrade_refuses_data_and_preserves_it(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _insert_attempt(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _downgrade(connection)
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT count(*) FROM provider_attempts")).scalar_one() == 1


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_empty_downgrade_and_reupgrade(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _downgrade(connection)
    assert "provider_attempts" not in sa.inspect(engine).get_table_names()
    with engine.begin() as connection:
        _upgrade(connection)
    assert "provider_attempts" in sa.inspect(engine).get_table_names()


def test_postgres_rls_denies_nonowner_and_forced_rls_downgrade_is_safe(pg_engine):
    engine, admin, schema = pg_engine
    role = "provider_attempt_test_" + uuid4().hex
    with engine.begin() as connection:
        _insert_attempt(connection)
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            connection.execute(sa.text(f'GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'))
            rows = connection.execute(sa.text("""
                SELECT c.relname,c.relrowsecurity FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND c.relname IN
                  ('provider_attempts','provider_attempt_visits','provider_active_visit_reservations')
            """), {"schema": schema}).all()
            assert len(rows) == 3 and all(row.relrowsecurity for row in rows)
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            assert connection.execute(sa.text(f'SELECT count(*) FROM "{schema}".provider_attempts')).scalar_one() == 0
            with pytest.raises(DBAPIError) as error, connection.begin_nested():
                connection.execute(sa.text(f"""
                    INSERT INTO "{schema}".provider_active_visit_reservations (visit_id,attempt_id,attempt_visit_id)
                    VALUES (1,10,20)
                """))
            assert error.value.orig.sqlstate == "42501"
        with admin.begin() as connection:
            for table in ("provider_attempts", "provider_attempt_visits", "provider_active_visit_reservations"):
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} OWNER TO "{role}"'))
                connection.execute(sa.text(f'ALTER TABLE "{schema}".{table} FORCE ROW LEVEL SECURITY'))
        with pytest.raises(DBAPIError) as error, engine.begin() as connection:
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            _downgrade(connection)
        assert error.value.orig.sqlstate == "42501"
        assert "row-level security" in str(error.value.orig)
        with engine.connect() as connection:
            assert connection.execute(sa.text("SELECT count(*) FROM provider_attempts")).scalar_one() == 1
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))

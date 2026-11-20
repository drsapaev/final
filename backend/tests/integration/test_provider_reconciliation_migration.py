"""Synthetic 0109 schema checks; these do not verify provider callbacks."""

from __future__ import annotations

import importlib.util
import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

PATH = (
    Path(__file__).resolve().parents[2]
    / "alembic/versions/0109_provider_reconciliation.py"
)
SPEC = importlib.util.spec_from_file_location(
    "synthetic_0109_provider_reconciliation", PATH
)
MIGRATION = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
SPEC.loader.exec_module(MIGRATION)


def _predecessor(connection):
    # Deliberately minimal FK parents; this is not a full upgrade chain.
    metadata = sa.MetaData()
    for name in ("payments", "payment_invoices", "payment_webhooks"):
        table = sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
        table.create(connection)
        connection.execute(table.insert(), [{"id": 1}, {"id": 2}])


def _upgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        MIGRATION.upgrade()


def _downgrade(connection):
    with Operations.context(MigrationContext.configure(connection)):
        MIGRATION.downgrade()


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'reconciliation.sqlite'}")

    @sa.event.listens_for(engine, "connect")
    def enable_fk(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as connection:
        _predecessor(connection)
        _upgrade(connection)
    yield engine
    engine.dispose()


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql":
        pytest.skip("requires a disposable PostgreSQL database")
    if not os.getenv("CI") and not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires an explicitly disposable clinic_test database")
    schema = "test_provider_reconciliation_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(
        url,
        connect_args={
            "options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"
        },
    )
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
    return (
        request.getfixturevalue("sqlite_engine")
        if kind == "sqlite"
        else request.getfixturevalue("pg_engine")[0]
    )


def _event(connection, **overrides):
    values = {
        "ident": 10,
        "provider": "click",
        "source": "webhook",
        "phase": "complete",
        "key": "a" * 64,
        "ref": "b" * 64,
        "kind": "payment",
        "payment": 1,
        "payment_snapshot": 1,
        "invoice": None,
        "invoice_snapshot": None,
        "webhook": 1,
        "webhook_snapshot": 1,
        "amount": "12345",
        "currency": "UZS",
        "exponent": 2,
        "status": "completed",
        "evidence": "c" * 64,
    }
    values.update(overrides)
    connection.execute(
        sa.text("""
        INSERT INTO provider_reconciliation_events
        (id,provider,source,phase,event_key,provider_reference_digest,target_kind,
         payment_id,payment_id_snapshot,invoice_id,invoice_id_snapshot,webhook_id,
         webhook_id_snapshot,amount_minor,currency,currency_exponent,observed_status,
         evidence_sha256,verified_at)
        VALUES (:ident,:provider,:source,:phase,:key,:ref,:kind,:payment,:payment_snapshot,
                :invoice,:invoice_snapshot,:webhook,:webhook_snapshot,:amount,:currency,
                :exponent,:status,:evidence,CURRENT_TIMESTAMP)
    """),
        values,
    )


def _conflict(connection, **overrides):
    values = {
        "ident": 20,
        "event": 10,
        "source": "webhook",
        "ref": "d" * 64,
        "webhook": 2,
        "webhook_snapshot": 2,
        "kind": "payment",
        "target_snapshot": 2,
        "amount": "999",
        "currency": "UZS",
        "exponent": 2,
        "status": "completed",
        "evidence": "e" * 64,
    }
    values.update(overrides)
    connection.execute(
        sa.text("""
        INSERT INTO provider_reconciliation_conflicts
        (id,event_id,source,provider_reference_digest,webhook_id,webhook_id_snapshot,
         target_kind,target_id_snapshot,amount_minor,currency,currency_exponent,
         observed_status,evidence_sha256,verified_at)
        VALUES (:ident,:event,:source,:ref,:webhook,:webhook_snapshot,:kind,:target_snapshot,
                :amount,:currency,:exponent,:status,:evidence,CURRENT_TIMESTAMP)
    """),
        values,
    )


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_phase_identity_conflict_and_unbounded_precision(kind, request):
    engine = _engine(kind, request)
    digits = "9" * 128
    with engine.begin() as connection:
        _event(connection, amount=digits)
        _event(connection, ident=11, phase="prepare")
        _conflict(connection)
        assert (
            connection.execute(
                sa.text(
                    "SELECT amount_minor FROM provider_reconciliation_events WHERE id=10"
                )
            ).scalar_one()
            == digits
        )
        assert (
            connection.execute(
                sa.text("SELECT count(*) FROM provider_reconciliation_conflicts")
            ).scalar_one()
            == 1
        )
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _event(connection, ident=12, amount="999")


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize("amount", ["", "01", "-1", "1.5", "12x", "9" * 129])
def test_noncanonical_amount_is_rejected(kind, amount, request):
    engine = _engine(kind, request)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _event(connection, amount=amount)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_deletions_keep_protected_snapshots(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _event(connection)
        _conflict(connection)
        connection.execute(sa.text("DELETE FROM payments WHERE id=1"))
        connection.execute(sa.text("DELETE FROM payment_webhooks WHERE id IN (1,2)"))
        assert tuple(
            connection.execute(
                sa.text(
                    "SELECT payment_id,payment_id_snapshot,webhook_id,webhook_id_snapshot FROM provider_reconciliation_events"
                )
            ).one()
        ) == (None, 1, None, 1)
        assert tuple(
            connection.execute(
                sa.text(
                    "SELECT webhook_id,webhook_id_snapshot FROM provider_reconciliation_conflicts"
                )
            ).one()
        ) == (None, 2)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        connection.execute(
            sa.text("DELETE FROM provider_reconciliation_events WHERE id=10")
        )


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
@pytest.mark.parametrize(
    "changes",
    [
        {"payment_snapshot": None},
        {"payment": 2},
        {"webhook_snapshot": None},
        {"kind": "unmatched"},
        {"kind": "payment_invoice"},
        {"currency": "uzs"},
        {"exponent": -1},
        {"source": "api"},
    ],
)
def test_invalid_target_receipt_and_currency_refused(kind, changes, request):
    engine = _engine(kind, request)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _event(connection, **changes)


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_downgrade_fails_closed_if_evidence_exists(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _event(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _downgrade(connection)
    with engine.connect() as connection:
        assert (
            connection.execute(
                sa.text("SELECT count(*) FROM provider_reconciliation_events")
            ).scalar_one()
            == 1
        )


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_empty_downgrade_and_upgrade(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _downgrade(connection)
        _upgrade(connection)
    assert "provider_reconciliation_events" in sa.inspect(engine).get_table_names()


@pytest.mark.parametrize("dialect", ["sqlite", "postgresql"])
def test_offline_sql_keeps_guard(dialect):
    output = io.StringIO()
    context = MigrationContext.configure(
        url=f"{dialect}://", opts={"as_sql": True, "output_buffer": output}
    )
    with Operations.context(context):
        MIGRATION.upgrade()
        MIGRATION.downgrade()
    text = output.getvalue()
    assert "CREATE TABLE provider_reconciliation_events" in text
    assert "provider_reconciliation_conflicts" in text
    assert (
        "provider reconciliation downgrade would discard evidence" in text
        if dialect == "postgresql"
        else "provider_recon_downgrade_guard_0109" in text
    )


def test_postgres_rls_blocks_unprivileged_read_and_write(pg_engine):
    engine, admin, schema = pg_engine
    role = "provider_recon_" + uuid4().hex
    with engine.begin() as connection:
        _event(connection)
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            connection.execute(
                sa.text(
                    f'GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"'
                )
            )
        with engine.begin() as connection:
            enabled = connection.execute(
                sa.text("""
                SELECT c.relname,c.relrowsecurity FROM pg_class c
                JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND c.relname IN
                ('provider_reconciliation_events','provider_reconciliation_conflicts')
            """),
                {"schema": schema},
            ).all()
            assert len(enabled) == 2 and all(row.relrowsecurity for row in enabled)
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            assert (
                connection.execute(
                    sa.text("SELECT count(*) FROM provider_reconciliation_events")
                ).scalar_one()
                == 0
            )
            with pytest.raises(DBAPIError), connection.begin_nested():
                _event(connection, ident=11, key="f" * 64)
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))


def test_forced_rls_cannot_hide_evidence_from_downgrade(pg_engine):
    engine, admin, schema = pg_engine
    role = "provider_recon_owner_" + uuid4().hex
    with engine.begin() as connection:
        _event(connection)
    try:
        with admin.begin() as connection:
            connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            for table in (
                "provider_reconciliation_events",
                "provider_reconciliation_conflicts",
            ):
                connection.execute(
                    sa.text(f'ALTER TABLE "{schema}".{table} OWNER TO "{role}"')
                )
                connection.execute(
                    sa.text(f'ALTER TABLE "{schema}".{table} FORCE ROW LEVEL SECURITY')
                )
        with pytest.raises(DBAPIError) as exc, engine.begin() as connection:
            connection.execute(sa.text(f'SET LOCAL ROLE "{role}"'))
            _downgrade(connection)
        assert exc.value.orig.sqlstate == "42501"
        with engine.connect() as connection:
            assert (
                connection.execute(
                    sa.text("SELECT count(*) FROM provider_reconciliation_events")
                ).scalar_one()
                == 1
            )
    finally:
        with admin.begin() as connection:
            connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
            connection.execute(sa.text(f'DROP ROLE "{role}"'))


def test_model_metadata_creates_sqlite_amount_guards(tmp_path):
    from app.models.provider_reconciliation import (
        ProviderReconciliationConflict,
        ProviderReconciliationEvent,
    )

    engine = sa.create_engine(f"sqlite:///{tmp_path / 'reconciliation_model.sqlite'}")
    try:
        with engine.begin() as connection:
            _predecessor(connection)
            ProviderReconciliationEvent.__table__.create(connection)
            ProviderReconciliationConflict.__table__.create(connection)
            _event(connection, amount="9" * 128)
        with pytest.raises(DBAPIError), engine.begin() as connection:
            _event(connection, ident=11, key="f" * 64, amount="1x")
    finally:
        engine.dispose()

"""Synthetic 0123 capability and writer races on a disposable PostgreSQL."""
import importlib.util
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import DropSchema

from app.db.capability_namespace import capability_schema_name
from tests.integration.test_click_receipt_pg import KEY, PAYLOAD, pg_case, record  # noqa: F401

_ROOT = Path(__file__).resolve().parents[3]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, _ROOT / path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = load("fence_0123", "backend/alembic/versions/0123_reconciliation_fence.py")
_BOOTSTRAP = load("fence_bootstrap_0112", "backend/alembic/versions/0112_doctor_price_context.py")
_PROVISION = load("recon_provision", "scripts/provision_reconciliation_fence_role.py")
_RECEIPT_PROVISION = load("receipt_provision", "scripts/provision_click_receipt_role.py")


@pytest.fixture
def fence_case(pg_case):  # noqa: F811
    owner, runtime, schema, owner_name, role, _ = pg_case
    cap = role + "_cap"
    private = capability_schema_name(schema)
    try:
        with owner.begin() as db:
            db.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
            db.execute(text("CREATE TABLE provider_reconciliation_events(id integer PRIMARY KEY, phase text)"))
            db.execute(text("ALTER TABLE provider_reconciliation_events ENABLE ROW LEVEL SECURITY"))
            operations = Operations(MigrationContext.configure(db))
            _BOOTSTRAP.op = operations
            _BOOTSTRAP._bootstrap_capability_namespace(schema)
            _MIGRATION.op = operations
            _MIGRATION.upgrade()
        _PROVISION.provision(owner, schema=schema, expected_owner=owner_name, backend_role=role, capability_role=cap)
        yield owner, runtime, schema, owner_name, role, cap
    finally:
        with owner.begin() as db:
            db.exec_driver_sql(f'DROP OWNED BY "{cap}" CASCADE')
            db.execute(DropSchema(private, cascade=True, if_exists=True))
            db.exec_driver_sql(f'DROP ROLE IF EXISTS "{cap}"')


def guard(db, schema):
    private = capability_schema_name(schema)
    q = db.dialect.identifier_preparer.quote_identifier(private)
    return db.exec_driver_sql(f'SELECT {q}.reconciliation_pending_guard()').scalar_one()


@pytest.mark.integration
def test_same_restricted_login_ingress_and_guard_force_rls(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    _RECEIPT_PROVISION.provision(owner, schema=schema, owner=owner_name, role=role, version="v1", key=KEY)
    with runtime.begin() as db:
        assert guard(db, schema) is False
        with pytest.raises(DBAPIError), db.begin_nested():
            db.exec_driver_sql(f'SET ROLE "{cap}"')
    assert record(runtime, schema, owner_name).created
    with runtime.begin() as db:
        assert guard(db, schema) is True


@pytest.mark.integration
def test_writer_nowait_conflict_and_recovery(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with runtime.begin() as held:
        assert guard(held, schema) is False
        with owner.connect() as writer:
            with pytest.raises(DBAPIError) as error:
                writer.execute(text("INSERT INTO provider_reconciliation_events(id) VALUES (1)"))
            assert error.value.orig.sqlstate == "55P03"
            writer.rollback()
    with owner.begin() as db:
        db.execute(text("INSERT INTO provider_reconciliation_events(id) VALUES (1)"))
    with runtime.begin() as db:
        assert guard(db, schema) is True


@pytest.mark.integration
def test_writer_commits_before_guard_rechecks_snapshot(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    acquired, release = threading.Event(), threading.Event()

    def writer():
        with owner.begin() as db:
            db.execute(text("INSERT INTO provider_reconciliation_events(id) VALUES (1)"))
            acquired.set()
            assert release.wait(5)

    def reader():
        assert acquired.wait(5)
        with runtime.begin() as db:
            return guard(db, schema)

    with ThreadPoolExecutor(max_workers=2) as pool:
        wf = pool.submit(writer)
        rf = pool.submit(reader)
        assert acquired.wait(5)
        release.set()
        wf.result(timeout=10)
        assert rf.result(timeout=10) is True


@pytest.mark.integration
def test_repeatable_read_hidden_rls_and_trigger_tampering_fail_closed(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with runtime.execution_options(isolation_level="REPEATABLE READ").connect() as db:
        with pytest.raises(DBAPIError, match="read committed"):
            guard(db, schema)
    with owner.begin() as db:
        db.exec_driver_sql(f'CREATE POLICY hidden_receipt ON "{schema}".click_callback_receipts AS RESTRICTIVE FOR SELECT TO "{cap}" USING (false)')
    with runtime.begin() as db:
        with pytest.raises(DBAPIError, match="visibility"), db.begin_nested():
            guard(db, schema)
    with owner.begin() as db:
        db.exec_driver_sql(f'DROP POLICY hidden_receipt ON "{schema}".click_callback_receipts')
        db.exec_driver_sql(f'ALTER TABLE "{schema}".provider_reconciliation_events DISABLE TRIGGER reconciliation_event_lock')
    with runtime.begin() as db:
        with pytest.raises(DBAPIError, match="triggers"), db.begin_nested():
            guard(db, schema)


def insert_receipt(db, phase, slot):
    db.execute(text("""
      INSERT INTO click_callback_receipts(event_key, body_digest, variant_slot, phase, confidence,
        media_type, body_size, key_version, ciphertext)
      VALUES (:key, :digest, :slot, :phase, 'authenticated', 'application/json', 1, 'v1', :ciphertext)
    """), {"key": str(slot) * 64, "digest": str(slot) * 64, "slot": slot,
            "phase": phase, "ciphertext": b"x"})


@pytest.mark.integration
def test_complete_receipt_race_both_orders_and_prepare_not_blocked(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with runtime.begin() as held:
        assert guard(held, schema) is False
        with owner.begin() as writer:
            insert_receipt(writer, "prepare", 1)
        with owner.connect() as writer:
            with pytest.raises(DBAPIError) as error:
                insert_receipt(writer, "complete", 2)
            assert error.value.orig.sqlstate == "55P03"
            writer.rollback()
    acquired, release = threading.Event(), threading.Event()

    def writer_first():
        with owner.begin() as db:
            insert_receipt(db, "complete", 2)
            acquired.set()
            assert release.wait(5)

    def reader_second():
        assert acquired.wait(5)
        with runtime.begin() as db:
            return guard(db, schema)

    with ThreadPoolExecutor(max_workers=2) as pool:
        wf = pool.submit(writer_first)
        rf = pool.submit(reader_second)
        assert acquired.wait(5)
        release.set()
        wf.result(timeout=10)
        assert rf.result(timeout=10) is True


@pytest.mark.integration
def test_populated_downgrade_refuses_receipt_evidence(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with owner.begin() as db:
        insert_receipt(db, "complete", 2)
    with owner.connect() as db:
        _MIGRATION.op = Operations(MigrationContext.configure(db))
        with pytest.raises(DBAPIError):
            _MIGRATION.downgrade()
        db.rollback()
    with runtime.begin() as db:
        assert guard(db, schema) is True


@pytest.mark.integration
def test_capability_cannot_read_receipt_ciphertext_or_mutate_mutex(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with owner.begin() as db:
        db.exec_driver_sql(f'SET LOCAL ROLE "{cap}"')
        db.exec_driver_sql(f'SELECT phase FROM "{schema}".click_callback_receipts')
        with pytest.raises(DBAPIError), db.begin_nested():
            db.exec_driver_sql(f'SELECT ciphertext FROM "{schema}".click_callback_receipts')
        with pytest.raises(DBAPIError), db.begin_nested():
            db.exec_driver_sql(f'UPDATE "{schema}".provider_reconciliation_mutex SET id=1')


@pytest.mark.integration
def test_empty_downgrade_and_reupgrade(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with owner.begin() as db:
        _MIGRATION.op = Operations(MigrationContext.configure(db))
        _MIGRATION.downgrade()
        _MIGRATION.upgrade()
    _PROVISION.provision(owner, schema=schema, expected_owner=owner_name, backend_role=role, capability_role=cap)
    with runtime.begin() as db:
        assert guard(db, schema) is False


@pytest.mark.integration
def test_receipt_ingress_rejects_privileged_capability_or_extra_grant(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with owner.begin() as db:
        db.exec_driver_sql(f'GRANT SELECT (ciphertext) ON "{schema}".click_callback_receipts TO "{cap}"')
    from app.services.click_receipt_service import ClickReceiptError
    with pytest.raises(ClickReceiptError, match="role unavailable"):
        record(runtime, schema, owner_name)
    with owner.begin() as db:
        db.exec_driver_sql(f'REVOKE SELECT (ciphertext) ON "{schema}".click_callback_receipts FROM "{cap}"')
    assert record(runtime, schema, owner_name).created


@pytest.mark.integration
def test_shadow_tables_and_functions_do_not_hide_real_evidence(fence_case):
    owner, runtime, schema, owner_name, role, cap = fence_case
    with owner.begin() as db:
        db.execute(text("INSERT INTO provider_reconciliation_events(id) VALUES (1)"))
    with runtime.begin() as db:
        db.execute(text("CREATE TEMP TABLE provider_reconciliation_events(id integer)"))
        db.execute(text("CREATE TEMP TABLE click_callback_receipts(phase text)"))
        db.execute(text("CREATE TEMP TABLE provider_reconciliation_mutex(id integer)"))
        assert guard(db, schema) is True


@pytest.mark.integration
def test_hostile_quoted_schema_cannot_end_function_bodies():
    import os
    import uuid

    from sqlalchemy import create_engine
    from sqlalchemy.engine import make_url
    from sqlalchemy.schema import CreateSchema, DropSchema

    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex[:8]
    schema = f'a"\'$$$reconciliation_fence_0${suffix}'
    role, cap, password = f"fence_backend_{suffix}", f"fence_cap_{suffix}", f"synthetic_{suffix}"
    owner = create_engine(url)
    runtime = create_engine(url.set(username=role, password=password))
    quote = owner.dialect.identifier_preparer.quote_identifier
    q = quote(schema)
    m119 = load("hostile_click_0119", "backend/alembic/versions/0119_click_receipt.py")
    try:
        with owner.begin() as db:
            owner_name = db.execute(text("SELECT CURRENT_USER")).scalar_one()
            db.execute(CreateSchema(schema))
            db.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
            db.exec_driver_sql(f'CREATE ROLE "{cap}" NOLOGIN')
            db.execute(text("SELECT pg_catalog.set_config('search_path', :schema, true)"), {"schema": q})
            db.execute(text("CREATE TABLE provider_reconciliation_events (id integer primary key, phase text)"))
            db.execute(text("ALTER TABLE provider_reconciliation_events ENABLE ROW LEVEL SECURITY"))
            ctx = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema}))
            m119.op = ctx
            m119.upgrade()
            _BOOTSTRAP.op = ctx
            _BOOTSTRAP._bootstrap_capability_namespace(schema)
            _MIGRATION.op = ctx
            _MIGRATION.upgrade()
        _RECEIPT_PROVISION.provision(owner, schema=schema, owner=owner_name, role=role, version="v1", key=KEY)
        _PROVISION.provision(owner, schema=schema, expected_owner=owner_name, backend_role=role, capability_role=cap)
        assert record(runtime, schema, owner_name).created
        with runtime.begin() as db:
            private_q = quote(capability_schema_name(schema))
            assert db.exec_driver_sql(f"SELECT {private_q}.reconciliation_pending_guard()").scalar_one() is True
    finally:
        runtime.dispose()
        with owner.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            db.execute(DropSchema(capability_schema_name(schema), cascade=True, if_exists=True))
            db.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
            db.exec_driver_sql(f'DROP ROLE IF EXISTS "{cap}"')
        owner.dispose()


def test_offline_sql_uses_delimiter_outside_hostile_schema():
    from io import StringIO

    output = StringIO()
    schema = 'a"\'$$$reconciliation_fence_0$'
    context = MigrationContext.configure(dialect_name="postgresql", opts={
        "as_sql": True, "output_buffer": output, "version_table_schema": schema,
    })
    _MIGRATION.op = Operations(context)
    _MIGRATION.upgrade()
    sql = output.getvalue()
    assert sql.count("AS $reconciliation_fence_1$") == 2
    assert sql.count("END $reconciliation_fence_1$") >= 2

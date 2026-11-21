"""0119 ingress under isolated PostgreSQL and a real nonowner LOGIN role."""
import importlib.util
import os
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import urlencode

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.services.click_receipt_service import ClickReceiptError, ClickReceiptService

_SCRIPT = Path(__file__).resolve().parents[3] / "scripts/provision_click_receipt_role.py"
_SPEC = importlib.util.spec_from_file_location("click_receipt_provisioner", _SCRIPT)
_PROVISION = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_PROVISION)
ProvisionError = _PROVISION.ProvisionError
provision = _PROVISION.provision

KEY = b"K" * 64
SECRET = "SYNTHETIC_SECRET"
PAYLOAD = urlencode({
    "click_trans_id": "12345", "service_id": "100", "click_paydoc_id": "42",
    "merchant_trans_id": "invoice_1", "amount": "23.45", "action": "1",
    "merchant_prepare_id": "77", "error": "0", "error_note": "Success",
    "sign_time": "2026-11-17 12:01:00", "sign_string": "25a20b004ef4db7d83ac6723e4c68bcf",
}).encode()


@pytest.fixture
def pg_case():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex[:18]
    schema, role, password = "click_receipt_" + suffix, "click_receipt_role_" + suffix, "SYNTHETIC_" + suffix
    admin = create_engine(url)
    with admin.begin() as db:
        owner = db.execute(text("SELECT CURRENT_USER")).scalar_one()
        db.execute(CreateSchema(schema))
        db.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
    owner_engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    runtime_engine = create_engine(url.set(username=role, password=password), connect_args={"options": f"-csearch_path={schema}"})
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0119_click_receipt.py"
    spec = importlib.util.spec_from_file_location("pg_0119_click_receipt", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with owner_engine.begin() as db:
            migration.op = Operations(MigrationContext.configure(db))
            migration.upgrade()
        provision(owner_engine, schema=schema, owner=owner, role=role, version="v1", key=KEY)
        yield owner_engine, runtime_engine, schema, owner, role, migration
    finally:
        runtime_engine.dispose()
        owner_engine.dispose()
        with admin.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
            db.exec_driver_sql(f'DROP ROLE "{role}"')
        admin.dispose()


def record(engine, schema, owner, body=PAYLOAD):
    with Session(engine) as db:
        return ClickReceiptService(db, keyring={"v1": KEY}, active_version="v1", trusted_schema=schema,
                                   trusted_owner=owner).store(body=body, content_type="application/x-www-form-urlencoded",
                                                              service_id="100", secret_key=SECRET)


@pytest.mark.integration
def test_restricted_login_concurrent_duplicate_is_one_durable_receipt(pg_case):
    owner_engine, runtime_engine, schema, owner, role, migration = pg_case
    barrier = threading.Barrier(2)

    def run():
        barrier.wait(timeout=5)
        return record(runtime_engine, schema, owner)

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [future.result(timeout=10) for future in (pool.submit(run), pool.submit(run))]
    assert results[0].id == results[1].id
    assert sorted(result.created for result in results) == [False, True]
    with runtime_engine.begin() as db:
        assert db.execute(text(f'SELECT count(*) FROM "{schema}".click_callback_receipts')).scalar_one() == 1
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text(f'DELETE FROM "{schema}".click_callback_receipts'))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text(f"INSERT INTO \"{schema}\".click_receipt_key_versions(version,commitment) VALUES ('forged', :value)"), {"value": "0" * 64})


@pytest.mark.integration
def test_shadow_table_does_not_capture_receipt(pg_case):
    owner_engine, runtime_engine, schema, owner, role, migration = pg_case
    with Session(runtime_engine) as db:
        db.execute(text("CREATE TEMP TABLE click_callback_receipts (id integer)"))
        db.commit()
        result = ClickReceiptService(db, keyring={"v1": KEY}, active_version="v1", trusted_schema=schema,
                                     trusted_owner=owner).store(body=PAYLOAD, content_type="application/x-www-form-urlencoded",
                                                                service_id="100", secret_key=SECRET)
        assert result.created
        with db.begin():
            assert db.execute(text("SELECT count(*) FROM pg_temp.click_callback_receipts")).scalar_one() == 0
            assert db.execute(text(f'SELECT count(*) FROM "{schema}".click_callback_receipts')).scalar_one() == 1


@pytest.mark.integration
def test_key_conflict_and_role_privilege_escalation_fail_closed(pg_case):
    owner_engine, runtime_engine, schema, owner, role, migration = pg_case
    provision(owner_engine, schema=schema, owner=owner, role=role, version="v1", key=KEY)
    with pytest.raises(ProvisionError):
        provision(owner_engine, schema=schema, owner=owner, role=role, version="v1", key=b"X" * 64)
    with owner_engine.begin() as db:
        db.exec_driver_sql(f'GRANT UPDATE ON "{schema}".click_callback_receipts TO "{role}"')
    with pytest.raises(ClickReceiptError, match="role unavailable"):
        record(runtime_engine, schema, owner)
    with owner_engine.begin() as db:
        db.exec_driver_sql(f'REVOKE UPDATE ON "{schema}".click_callback_receipts FROM "{role}"')
    assert record(runtime_engine, schema, owner).created


@pytest.mark.integration
def test_populated_downgrade_refuses_loss(pg_case):
    owner_engine, runtime_engine, schema, owner, role, migration = pg_case
    record(runtime_engine, schema, owner)
    with owner_engine.connect() as db:
        migration.op = Operations(MigrationContext.configure(db))
        with pytest.raises(DBAPIError):
            migration.downgrade()
        db.rollback()
        assert db.execute(text("SELECT count(*) FROM click_callback_receipts")).scalar_one() == 1


@pytest.mark.integration
def test_unexpected_public_grant_and_hidden_rls_fail_closed(pg_case):
    owner_engine, runtime_engine, schema, owner, role, migration = pg_case
    with owner_engine.begin() as db:
        db.exec_driver_sql(f'GRANT SELECT ON "{schema}".click_callback_receipts TO PUBLIC')
    with pytest.raises(ClickReceiptError, match="role unavailable"):
        record(runtime_engine, schema, owner)
    with owner_engine.begin() as db:
        db.exec_driver_sql(f'REVOKE SELECT ON "{schema}".click_callback_receipts FROM PUBLIC')
        db.exec_driver_sql(f'CREATE POLICY hide_receipt ON "{schema}".click_callback_receipts AS RESTRICTIVE FOR SELECT TO "{role}" USING (false)')
    with pytest.raises(ClickReceiptError, match="role unavailable"):
        record(runtime_engine, schema, owner)
    with owner_engine.begin() as db:
        db.exec_driver_sql(f'DROP POLICY hide_receipt ON "{schema}".click_callback_receipts')
    assert record(runtime_engine, schema, owner).created


@pytest.mark.integration
def test_public_sequence_grant_refused_by_provisioner_and_runtime(pg_case):
    owner_engine, runtime_engine, schema, owner, role, migration = pg_case
    with owner_engine.begin() as db:
        db.exec_driver_sql(f'GRANT USAGE ON SEQUENCE "{schema}".click_callback_receipts_id_seq TO PUBLIC')
    with pytest.raises(ProvisionError, match="sequence grant"):
        provision(owner_engine, schema=schema, owner=owner, role=role, version="v1", key=KEY)
    with pytest.raises(ClickReceiptError, match="role unavailable"):
        record(runtime_engine, schema, owner)
    with owner_engine.begin() as db:
        db.exec_driver_sql(f'REVOKE USAGE ON SEQUENCE "{schema}".click_callback_receipts_id_seq FROM PUBLIC')
    assert record(runtime_engine, schema, owner).created


@pytest.mark.integration
def test_repeatable_read_is_not_used_as_idempotency_fence(pg_case):
    owner_engine, runtime_engine, schema, owner, role, migration = pg_case
    rr_engine = runtime_engine.execution_options(isolation_level="REPEATABLE READ")
    with pytest.raises(ClickReceiptError, match="isolation unavailable"):
        record(rr_engine, schema, owner)
    assert record(runtime_engine, schema, owner).created


@pytest.mark.integration
def test_empty_pg_upgrade_downgrade_reupgrade(pg_case):
    owner_engine, _, _, _, _, _ = pg_case
    schema = "empty_receipt_" + uuid.uuid4().hex[:18]
    with owner_engine.begin() as db:
        db.execute(CreateSchema(schema))
    empty_engine = create_engine(owner_engine.url, connect_args={"options": f"-csearch_path={schema}"})
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0119_click_receipt.py"
    spec = importlib.util.spec_from_file_location("pg_0119_empty", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with empty_engine.begin() as db:
            migration.op = Operations(MigrationContext.configure(db))
            migration.upgrade()
            migration.downgrade()
            migration.upgrade()
            assert db.execute(text("SELECT count(*) FROM click_callback_receipts")).scalar_one() == 0
    finally:
        empty_engine.dispose()
        with owner_engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True))

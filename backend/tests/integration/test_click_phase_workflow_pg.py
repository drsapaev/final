"""0127 immutable issuance races against real 0111/0119 migrations."""
import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

_ROOT = Path(__file__).resolve().parents[2] / "alembic/versions"


def migration(name):
    spec = importlib.util.spec_from_file_location("phase_" + name[:4], _ROOT / name)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def provisioner():
    path = _ROOT.parents[2] / "scripts/provision_click_phase_role.py"
    spec = importlib.util.spec_from_file_location("click_phase_provisioner", path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


@pytest.fixture
def phase_case():
    raw = os.environ.get("DATABASE_URL", "")
    if not raw:
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test database")
    suffix = uuid.uuid4().hex[:16]
    schema, role, password = "clickphase_" + suffix, "clickphase_role_" + suffix, "synthetic_" + suffix
    admin = create_engine(url)
    runtime = create_engine(url.set(username=role, password=password), connect_args={"options": f"-csearch_path={schema}"})
    owner = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        with admin.begin() as db:
            db.execute(CreateSchema(schema))
            db.exec_driver_sql(f'CREATE ROLE "{role}" LOGIN PASSWORD \'{password}\'')
        with owner.begin() as db:
            for table in ("payments", "payment_invoices", "users", "visits", "provider_reconciliation_events"):
                db.execute(text(f"CREATE TABLE {table} (id integer PRIMARY KEY)"))
                db.execute(text(f"INSERT INTO {table} VALUES (1), (2)"))
            operations = Operations(MigrationContext.configure(db))
            for filename in ("0111_provider_attempts.py", "0119_click_receipt.py", "0127_click_phase_binding.py"):
                m = migration(filename)
                m.op = operations
                m.upgrade()
            for num in (1, 2):
                db.execute(text("""INSERT INTO provider_attempts
                  (id,public_id,target_kind,payment_id,payment_id_snapshot,actor_user_id,actor_user_id_snapshot,
                   provider,merchant_hash,order_ref,fingerprint,amount_minor,currency,currency_exponent,status)
                  VALUES (:id,:public,'payment',1,1,1,1,'click',:merchant,:order,:fingerprint,'1234','UZS',2,'prepared')"""),
                  {"id": num, "public": str(uuid.uuid4()), "merchant": "a" * 64,
                   "order": f"clinic_1_{uuid.uuid4()}", "fingerprint": "b" * 64})
            db.execute(text("""INSERT INTO provider_attempt_visits(attempt_id,visit_id,visit_id_snapshot,patient_id_snapshot,context_epoch,amount_minor)
              VALUES (1,1,1,1,1,'1234'), (2,1,1,1,1,'1234')"""))
            owner_name = db.execute(text("SELECT CURRENT_USER")).scalar_one()
        provisioner().provision(owner, schema=schema, owner=owner_name, backend_role=role)
        yield owner, runtime, schema, role
    finally:
        runtime.dispose()
        owner.dispose()
        with admin.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            db.exec_driver_sql(f'DROP ROLE IF EXISTS "{role}"')
        admin.dispose()


def issue(db, attempt):
    db.execute(text("""INSERT INTO click_issued_attempts
      (attempt_id,order_ref,merchant_hash,fingerprint,amount_minor,currency,currency_exponent,provider,target_kind,actor_user_id_snapshot,allocations_sha256)
      SELECT id,order_ref,merchant_hash,fingerprint,amount_minor,currency,currency_exponent,provider,target_kind,actor_user_id_snapshot,:digest
      FROM provider_attempts WHERE id=:id"""), {"id": attempt, "digest": "c" * 64})


def add_visit(db, attempt):
    db.execute(text("""INSERT INTO provider_attempt_visits(attempt_id,visit_id,visit_id_snapshot,patient_id_snapshot,context_epoch,amount_minor)
      VALUES (:id,2,2,1,1,'0')"""), {"id": attempt})


@pytest.mark.integration
def test_marker_and_new_allocation_serialize_both_orders(phase_case):
    owner, runtime, schema, role = phase_case
    with runtime.connect() as marker, runtime.connect() as writer:
        issue(marker, 1)
        with pytest.raises(DBAPIError) as conflict:
            add_visit(writer, 1)
        assert conflict.value.orig.sqlstate == "55P03"
        writer.rollback()
        marker.commit()
        with pytest.raises(DBAPIError, match="immutable"):
            add_visit(writer, 1)
        writer.rollback()
        add_visit(writer, 2)
        with pytest.raises(DBAPIError) as conflict:
            issue(marker, 2)
        assert conflict.value.orig.sqlstate == "55P03"
        marker.rollback()
        writer.commit()
        issue(marker, 2)
        marker.commit()


@pytest.mark.integration
def test_issued_snapshots_and_allocations_are_immutable(phase_case):
    owner, runtime, schema, role = phase_case
    with runtime.connect() as db:
        issue(db, 1)
        db.commit()
        for statement in ("UPDATE provider_attempts SET amount_minor='9999' WHERE id=1",
                          "UPDATE provider_attempts SET payment_id_snapshot=2 WHERE id=1",
                          "UPDATE provider_attempt_visits SET amount_minor='1' WHERE attempt_id=1"):
            with pytest.raises(DBAPIError), db.begin_nested():
                db.execute(text(statement))
        db.rollback()
    # A trusted owner may detach a deleted subject but cannot rebind it.
    with owner.begin() as db:
        db.execute(text("UPDATE provider_attempts SET payment_id=NULL WHERE id=1"))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("UPDATE provider_attempts SET payment_id=1 WHERE id=1"))
        db.execute(text("UPDATE provider_attempt_visits SET visit_id=NULL WHERE attempt_id=1"))
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(text("UPDATE provider_attempt_visits SET visit_id=1 WHERE attempt_id=1"))


@pytest.mark.integration
def test_repeatable_read_and_hidden_marker_fail_closed(phase_case):
    owner, runtime, schema, role = phase_case
    with runtime.execution_options(isolation_level="REPEATABLE READ").connect() as db:
        with pytest.raises(DBAPIError, match="read committed"):
            issue(db, 1)
    with runtime.execution_options(isolation_level="REPEATABLE READ").connect() as db:
        with pytest.raises(DBAPIError, match="read committed"):
            add_visit(db, 1)
    with owner.begin() as db:
        db.exec_driver_sql(f'CREATE POLICY hide_issued ON "{schema}".click_issued_attempts AS RESTRICTIVE FOR SELECT TO "{role}" USING (false)')
    with runtime.connect() as db:
        with pytest.raises(DBAPIError, match="visibility unavailable"):
            add_visit(db, 1)


@pytest.mark.integration
def test_marker_composite_foreign_key_cannot_change_issued_amount(phase_case):
    owner, runtime, schema, role = phase_case
    with runtime.connect() as db:
        with pytest.raises(DBAPIError):
            db.execute(text("""INSERT INTO click_issued_attempts
              (attempt_id,order_ref,merchant_hash,fingerprint,amount_minor,currency,currency_exponent,provider,target_kind,actor_user_id_snapshot,allocations_sha256)
              SELECT id,order_ref,merchant_hash,fingerprint,'9999',currency,currency_exponent,provider,target_kind,actor_user_id_snapshot,:digest
              FROM provider_attempts WHERE id=1"""), {"digest": "c" * 64})
        db.rollback()
        assert db.execute(text("SELECT count(*) FROM click_issued_attempts")).scalar_one() == 0


def test_offline_sql_quotes_schema_and_uses_fresh_dollar_tag():
    from io import StringIO

    output = StringIO()
    context = MigrationContext.configure(dialect_name="postgresql", opts={
        "as_sql": True, "output_buffer": output,
        "version_table_schema": 'a"\'$$$click_binding_0$',
    })
    m = migration("0127_click_phase_binding.py")
    m.op = Operations(context)
    m.upgrade()
    sql = output.getvalue()
    assert "AS $click_binding_1$" in sql
    assert "END $click_binding_1$" in sql
    assert '"a""\'$$$click_binding_0$".provider_attempts' in sql


@pytest.mark.integration
def test_phase_provisioner_rejects_public_or_hidden_access(phase_case):
    owner, runtime, schema, role = phase_case
    module = provisioner()
    with owner.begin() as db:
        owner_name = db.execute(text("SELECT CURRENT_USER")).scalar_one()
        db.exec_driver_sql(f'GRANT SELECT ON "{schema}".click_issued_attempts TO PUBLIC')
    with pytest.raises(module.ProvisionError, match="Public or client"):
        module.provision(owner, schema=schema, owner=owner_name, backend_role=role)
    with owner.begin() as db:
        db.exec_driver_sql(f'REVOKE SELECT ON "{schema}".click_issued_attempts FROM PUBLIC')
        db.exec_driver_sql(f'CREATE POLICY hidden_phase ON "{schema}".click_issued_attempts AS RESTRICTIVE FOR SELECT TO "{role}" USING (false)')
    with pytest.raises(module.ProvisionError, match="Restrictive"):
        module.provision(owner, schema=schema, owner=owner_name, backend_role=role)


from tests.integration.test_reconciliation_fence_pg import fence_case, pg_case  # noqa: E402,F401


@pytest.mark.integration
def test_one_login_receipt_fence_and_issued_marker_under_forced_rls(fence_case):  # noqa: F811
    from tests.integration.test_click_receipt_pg import record
    from tests.integration.test_reconciliation_fence_pg import guard

    owner, runtime, schema, owner_name, role, _cap = fence_case
    with owner.begin() as db:
        for table in ("payments", "payment_invoices", "users", "visits"):
            db.execute(text(f"CREATE TABLE {table} (id integer PRIMARY KEY)"))
            db.execute(text(f"INSERT INTO {table} VALUES (1)"))
        operations = Operations(MigrationContext.configure(db))
        for name in ("0111_provider_attempts.py", "0127_click_phase_binding.py"):
            m = migration(name)
            m.op = operations
            m.upgrade()
        db.execute(text("""INSERT INTO provider_attempts
          (id,public_id,target_kind,payment_id,payment_id_snapshot,actor_user_id,actor_user_id_snapshot,
           provider,merchant_hash,order_ref,fingerprint,amount_minor,currency,currency_exponent,status)
          VALUES (1,:public,'payment',1,1,1,1,'click',:merchant,:order,:fingerprint,'1234','UZS',2,'prepared')"""),
          {"public": str(uuid.uuid4()), "merchant": "a" * 64, "order": f"clinic_1_{uuid.uuid4()}", "fingerprint": "b" * 64})
        db.execute(text("""INSERT INTO provider_attempt_visits(attempt_id,visit_id,visit_id_snapshot,patient_id_snapshot,context_epoch,amount_minor)
          VALUES (1,1,1,1,1,'1234')"""))
    provisioner().provision(owner, schema=schema, owner=owner_name, backend_role=role)
    with runtime.begin() as db:
        assert guard(db, schema) is False
        issue(db, 1)
    assert record(runtime, schema, owner_name).created
    with runtime.begin() as db:
        assert guard(db, schema) is True
        assert db.execute(text("SELECT count(*) FROM click_issued_attempts")).scalar_one() == 1

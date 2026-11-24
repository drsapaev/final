"""Verify the persisted owner snapshot with disposable synthetic schemas."""

import importlib.util
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.fixture
def ownership_db(request):
    if request.param == "postgresql":
        raw = os.environ.get("DATABASE_URL", "")
        url = make_url(raw) if raw else None
        if url is None or url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
            pytest.skip("requires disposable clinic_test PostgreSQL")
        admin = sa.create_engine(url, hide_parameters=True)
        schema = f"tg_owner_{uuid4().hex}"
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
    else:
        admin = schema = None
        engine = sa.create_engine("sqlite:///:memory:")
    try:
        with engine.begin() as conn:
            if request.param == "sqlite-recursive":
                conn.exec_driver_sql("PRAGMA recursive_triggers=ON")
            conn.exec_driver_sql("CREATE TABLE patients (id integer PRIMARY KEY, is_deleted boolean, notification_owner_generation bigint)")
            conn.exec_driver_sql("""CREATE TABLE telegram_users (
              id integer PRIMARY KEY, patient_id integer, user_id integer, chat_id bigint,
              active boolean DEFAULT true, blocked boolean DEFAULT false,
              notifications_enabled boolean DEFAULT true, appointment_reminders boolean DEFAULT true
            )""")
            conn.exec_driver_sql("INSERT INTO patients VALUES (1, false, 7), (2, false, 10)")
            conn.exec_driver_sql("INSERT INTO telegram_users (id,patient_id,chat_id) VALUES (1,1,10001)")
            for name in ("0101_telegram_patient_link_epoch.py", "0122_telegram_link_epoch.py"):
                _revision(conn, schema, name).upgrade()
        yield engine, schema
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


def _revision(conn, schema, name="0124_telegram_ownership.py"):
    path = Path(__file__).resolve().parents[2] / "alembic/versions" / name
    spec = importlib.util.spec_from_file_location(f"synthetic_{path.stem}", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn, opts={"version_table_schema": schema}))
    return module


@pytest.mark.parametrize("ownership_db", ["sqlite", "sqlite-recursive", "postgresql"], indirect=True)
def test_legacy_links_need_attestation_and_rebinding_clears_it(ownership_db):
    engine, schema = ownership_db
    with engine.begin() as conn:
        revision = _revision(conn, schema)
        epoch_sql = sa.text("SELECT patient_link_epoch FROM telegram_users WHERE id=1")
        legacy_epoch = conn.execute(epoch_sql).scalar_one()
        revision.upgrade()
        read = sa.text("SELECT patient_owner_generation_snapshot FROM telegram_users WHERE id=1")
        assert conn.execute(read).scalar_one() is None
        assert conn.execute(epoch_sql).scalar_one() == legacy_epoch
        attest = sa.text("UPDATE telegram_users SET patient_owner_generation_snapshot=:generation WHERE id=1")
        with pytest.raises(sa.exc.DBAPIError, match="invalid Telegram ownership evidence"), conn.begin_nested():
            conn.execute(attest, {"generation": 6})
        conn.execute(attest, {"generation": 7})
        assert conn.execute(read).scalar_one() == 7
        attested_epoch = conn.execute(epoch_sql).scalar_one()
        assert attested_epoch > legacy_epoch
        with pytest.raises(sa.exc.DBAPIError), conn.begin_nested():
            revision.downgrade()
        assert conn.execute(read).scalar_one() == 7

        conn.execute(attest, {"generation": None})
        revoked_epoch = conn.execute(epoch_sql).scalar_one()
        conn.execute(attest, {"generation": 7})
        assert attested_epoch < revoked_epoch < conn.execute(epoch_sql).scalar_one()
        assert conn.execute(read).scalar_one() == 7
        conn.exec_driver_sql("UPDATE telegram_users SET chat_id=10002 WHERE id=1")
        assert conn.execute(read).scalar_one() is None
        conn.execute(attest, {"generation": 7})
        conn.exec_driver_sql("UPDATE telegram_users SET patient_id=2 WHERE id=1")
        assert conn.execute(read).scalar_one() is None
        conn.execute(attest, {"generation": 10})
        prior_account_epoch = conn.execute(epoch_sql).scalar_one()
        conn.exec_driver_sql("UPDATE telegram_users SET user_id=9 WHERE id=1")
        assert conn.execute(read).scalar_one() is None
        rebind_epoch = conn.execute(epoch_sql).scalar_one()
        assert rebind_epoch > prior_account_epoch
        revision.downgrade()
        revision.upgrade()
        assert conn.execute(read).scalar_one() is None
        assert conn.execute(epoch_sql).scalar_one() == rebind_epoch


@pytest.mark.parametrize("ownership_db", ["postgresql"], indirect=True)
def test_runtime_role_cannot_attest_a_chat_even_with_column_update(ownership_db):
    owner, schema = ownership_db
    suffix = uuid4().hex
    role, password = f"tg_owner_runtime_{suffix}", "synthetic-" + suffix
    runtime = None
    try:
        with owner.begin() as conn:
            _revision(conn, schema).upgrade()
            conn.exec_driver_sql(f"CREATE ROLE {role} LOGIN PASSWORD '{password}'")
            conn.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema} TO {role}")
            conn.exec_driver_sql(f"GRANT SELECT, UPDATE ON {schema}.telegram_users TO {role}")
            conn.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {schema}.telegram_patient_link_generation_seq TO {role}")
        runtime = sa.create_engine(owner.url.set(username=role, password=password),
                                   connect_args={"options": f"-csearch_path={schema}"}, hide_parameters=True)
        with runtime.begin() as conn:
            assert conn.exec_driver_sql("SELECT CURRENT_USER").scalar_one() == role
            with pytest.raises(sa.exc.DBAPIError, match="invalid Telegram ownership evidence"), conn.begin_nested():
                conn.exec_driver_sql("UPDATE telegram_users SET patient_owner_generation_snapshot=7 WHERE id=1")
            conn.exec_driver_sql("UPDATE telegram_users SET chat_id=10002 WHERE id=1")
            assert tuple(conn.exec_driver_sql(
                "SELECT chat_id, patient_owner_generation_snapshot FROM telegram_users WHERE id=1"
            ).one()) == (10002, None)
    finally:
        if runtime is not None:
            runtime.dispose()
        with owner.begin() as conn:
            conn.exec_driver_sql(f"DROP OWNED BY {role}")
            conn.exec_driver_sql(f"DROP ROLE {role}")

"""Synthetic 0114 SECURITY DEFINER capability, with distinct non-superuser roles.

Only minimal 0107-predecessor tables are created in a random schema; this is
not a complete Alembic-chain test. No production database is used.
"""
from __future__ import annotations

import importlib.util
import os
import secrets
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from fastapi import HTTPException
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core.config import settings
from app.db.capability_namespace import capability_schema_name
from app.services.all_free_guard import lock_visit_without_pending


@pytest.fixture
def capability():
    url = make_url(os.getenv("ALL_FREE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, owner, runtime, outsider = ("test_cap_" + suffix, "cap_owner_" + suffix,
                                         "cap_runtime_" + suffix, "cap_other_" + suffix)
    private = capability_schema_name(schema)
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    created_roles = []
    role_engines = {}
    try:
        with admin.begin() as connection:
            for role in (owner, runtime, outsider):
                if role == owner:
                    connection.execute(sa.text(f'CREATE ROLE "{role}" NOLOGIN NOSUPERUSER NOBYPASSRLS'))
                else:
                    password = secrets.token_urlsafe(24)
                    statement = connection.execute(sa.text("""
                      SELECT pg_catalog.format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS',
                                               CAST(:role AS text),CAST(:password AS text))
                    """), {"role": role, "password": password}).scalar_one()
                    try:
                        connection.exec_driver_sql(statement)
                    except DBAPIError:
                        pytest.fail("Synthetic runtime role could not be created", pytrace=False)
                    role_engines[role] = sa.create_engine(
                        url.set(username=role, password=password),
                        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
                    )
                created_roles.append(role)
                connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            connection.execute(sa.text(f'ALTER SCHEMA "{schema}" OWNER TO "{owner}"'))
            connection.execute(sa.text(f'CREATE SCHEMA "{private}" AUTHORIZATION "{owner}"'))
            connection.execute(sa.text(f'CREATE TABLE "{private}".clinic_capability_namespace (id smallint, format_version smallint, application_schema text, private_schema text)'))
            connection.execute(sa.text(f'ALTER TABLE "{private}".clinic_capability_namespace OWNER TO "{owner}"'))
            connection.execute(sa.text(f'INSERT INTO "{private}".clinic_capability_namespace VALUES (1,1,:app,:private)'), {"app": schema, "private": private})
            connection.execute(sa.text(f'GRANT CREATE ON SCHEMA "{schema}" TO "{owner}"'))
        with engine.begin() as connection:
            connection.execute(sa.text("CREATE TABLE visits (id integer PRIMARY KEY)"))
            connection.execute(sa.text("""CREATE TABLE visit_services (
              id integer PRIMARY KEY, visit_id integer, service_id integer,
              qty integer, price numeric, currency text)"""))
            connection.execute(sa.text("""CREATE TABLE all_free_requests (
              id integer PRIMARY KEY, visit_id integer, visit_id_snapshot integer, patient_id integer,
              encounter_id integer, status text NOT NULL, requested_by_user_id integer,
              requested_by_user_id_snapshot integer, requested_by_role_snapshot text, decision_kind text,
              decision_context_epoch bigint, decided_by_user_id integer, decided_by_user_id_snapshot integer,
              decided_by_role_snapshot text, decided_at timestamptz)"""))
            connection.execute(sa.text("""CREATE TABLE all_free_request_lines (
              id integer PRIMARY KEY, request_id integer, visit_service_id integer, visit_id_snapshot integer,
              service_id_snapshot integer, quantity integer, unit_price numeric, currency text)"""))
            connection.execute(sa.text("""CREATE TABLE all_free_request_events (
              id integer PRIMARY KEY, request_id integer, event_type text, actor_user_id integer,
              actor_user_id_snapshot integer, actor_role_snapshot text)"""))
            connection.execute(sa.text("INSERT INTO visits (id) VALUES (10),(11)"))
            connection.execute(sa.text("INSERT INTO all_free_requests (id,visit_id,status) VALUES (1,10,'pending')"))
            for table in ("all_free_requests", "all_free_request_lines", "all_free_request_events"):
                connection.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))
                connection.execute(sa.text(f'ALTER TABLE "{table}" OWNER TO "{owner}"'))
            path = Path(__file__).resolve().parents[2] / "alembic/versions/0114_all_free_visibility.py"
            spec = importlib.util.spec_from_file_location("synthetic_allfree_0114", path)
            assert spec and spec.loader
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            connection.execute(sa.text(f'SET LOCAL ROLE "{owner}"'))
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
        with admin.begin() as connection:
            connection.execute(sa.text(f'REVOKE CREATE ON SCHEMA "{schema}" FROM "{owner}"'))
            for role in (runtime, outsider):
                connection.execute(sa.text(f'GRANT SELECT, UPDATE ON "{schema}".visits TO "{role}"'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{private}" TO "{runtime}"'))
            connection.execute(sa.text(f'GRANT EXECUTE ON FUNCTION "{private}".all_free_pending_exists(integer) TO "{runtime}"'))
        engine._guard_test_role_engines = role_engines
        yield engine, admin, schema, owner, runtime, outsider
    finally:
        for role_engine in role_engines.values():
            role_engine.dispose()
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(private, cascade=True))
            connection.execute(DropSchema(schema, cascade=True))
            for role in reversed(created_roles):
                connection.execute(sa.text(f'DROP OWNED BY "{role}"'))
                connection.execute(sa.text(f'DROP ROLE "{role}"'))
        admin.dispose()


def _set_role(db, role):
    # Use a real restricted LOGIN, not SET ROLE from a superuser session.
    if isinstance(db.bind, sa.engine.Engine):
        db.bind = db.bind._guard_test_role_engines[role]
    assert db.execute(sa.text("SELECT current_user = session_user")).scalar_one()


def test_runtime_checks_hidden_pending_without_general_table_select(capability):
    engine, _admin, schema, _owner, runtime, _outsider = capability
    with Session(engine) as db:
        _set_role(db, runtime)
        assert db.execute(sa.text("SELECT has_table_privilege(current_user,:table,'SELECT')"),
                          {"table": f'"{schema}".all_free_requests'}).scalar_one() is False
        assert db.execute(sa.text("SELECT has_function_privilege(current_user,:function,'EXECUTE')"),
                          {"function": f'"{capability_schema_name(schema)}".all_free_pending_exists(integer)'}).scalar_one() is True
        with pytest.raises(DBAPIError), db.begin_nested():
            db.execute(sa.text(f'SELECT * FROM "{schema}".all_free_requests')).all()
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 10)
        assert error.value.status_code == 409
        assert lock_visit_without_pending(db, 11) is None


def test_no_function_grant_or_public_access_fails_closed(capability):
    engine, admin, schema, _owner, runtime, outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'REVOKE EXECUTE ON FUNCTION "{capability_schema_name(schema)}".all_free_pending_exists(integer) FROM "{runtime}"'))
    for role in (runtime, outsider):
        with Session(engine) as db:
            _set_role(db, role)
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 10)
            assert error.value.status_code == 503


def test_forced_rls_with_complete_owner_policy_preserves_pending_guard(capability):
    engine, admin, schema, owner, runtime, _outsider = capability
    with admin.begin() as connection:
        role = connection.execute(sa.text("SELECT rolsuper,rolbypassrls FROM pg_roles WHERE rolname=:role"), {"role": owner}).one()
        assert role.rolsuper is False and role.rolbypassrls is False
        connection.execute(sa.text(f'ALTER TABLE "{schema}".all_free_requests FORCE ROW LEVEL SECURITY'))
    with Session(engine) as db:
        _set_role(db, runtime)
        assert lock_visit_without_pending(db, 11) is None
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 10)
        assert error.value.status_code == 409


def test_restrictive_owner_policy_cannot_hide_pending_request(capability):
    engine, admin, schema, owner, runtime, _outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'ALTER TABLE "{schema}".all_free_requests FORCE ROW LEVEL SECURITY'))
        connection.execute(sa.text(f'CREATE POLICY synthetic_restrictive ON "{schema}".all_free_requests AS RESTRICTIVE FOR SELECT TO "{owner}" USING (false)'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 10)
        assert error.value.status_code == 503


def test_pg_temp_last_cannot_shadow_the_pending_guard(capability):
    engine, _admin, schema, _owner, runtime, _outsider = capability
    with Session(engine) as db:
        _set_role(db, runtime)
        db.execute(sa.text("CREATE TEMP TABLE visits (id integer PRIMARY KEY)"))
        db.execute(sa.text("CREATE TEMP TABLE all_free_requests (id integer PRIMARY KEY)"))
        db.execute(sa.text(f'SET LOCAL search_path TO pg_catalog, "{schema}", pg_temp'))
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 10)
        assert error.value.status_code == 409


def test_owner_membership_requires_exact_trusted_profile(capability, monkeypatch):
    engine, admin, _schema, owner, runtime, outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT "{owner}" TO "{outsider}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 10)
        assert error.value.status_code == 503
    monkeypatch.setattr(settings, "TRUSTED_DB_OWNER_MEMBERS", (outsider,))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 10)
        assert error.value.status_code == 409
    monkeypatch.setattr(settings, "TRUSTED_DB_OWNER_MEMBERS", (outsider, "unrelated"))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 10)
        assert error.value.status_code == 503


@pytest.mark.parametrize("isolation", ["REPEATABLE READ", "SERIALIZABLE"])
def test_snapshot_isolation_fails_closed(capability, isolation):
    engine, _admin, _schema, _owner, runtime, _outsider = capability
    with engine._guard_test_role_engines[runtime].connect().execution_options(isolation_level=isolation) as connection:
        with Session(connection) as db:
            _set_role(db, runtime)
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 11)
            assert error.value.status_code == 503


def test_rls_ddl_waits_until_guard_transaction_finishes(capability):
    engine, _admin, _schema, _owner, runtime, _outsider = capability
    started, pids = threading.Event(), []
    def change_rls():
        with engine.begin() as connection:
            pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            connection.execute(sa.text("ALTER TABLE all_free_requests FORCE ROW LEVEL SECURITY"))
    with Session(engine) as db:
        _set_role(db, runtime)
        assert lock_visit_without_pending(db, 11) is None
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(change_rls)
            try:
                assert started.wait(5)
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    assert not future.done(), "RLS change did not wait for the guard transaction"
                    with engine.connect() as inspector:
                        blocked = inspector.execute(sa.text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pids[0]}).scalar_one()
                    if blocked:
                        break
                    time.sleep(0.02)
                else:
                    pytest.fail("RLS change did not block")
            finally:
                db.commit()
            future.result(timeout=15)


@pytest.mark.parametrize("table", ["all_free_requests", "all_free_request_lines", "all_free_request_events"])
def test_template_policy_ddl_waits_for_guard_transaction(capability, table):
    engine, _admin, _schema, _owner, runtime, _outsider = capability
    started, pids = threading.Event(), []

    def change_policy():
        with engine.begin() as connection:
            pids.append(connection.execute(sa.text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            connection.exec_driver_sql(f'ALTER POLICY allfree_template_select ON "{table}" USING (true)')

    with Session(engine) as db:
        _set_role(db, runtime)
        assert lock_visit_without_pending(db, 11) is None
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(change_policy)
            try:
                assert started.wait(5)
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    assert not future.done(), "Policy DDL did not wait for guard transaction"
                    with engine.connect() as inspector:
                        blocked = inspector.execute(sa.text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pids[0]}).scalar_one()
                    if blocked:
                        break
                    time.sleep(0.02)
                else:
                    pytest.fail("Policy DDL did not block")
            finally:
                db.commit()
            future.result(timeout=15)


def test_malicious_search_path_shadow_cannot_authorize_payment(capability):
    engine, admin, schema, _owner, runtime, _outsider = capability
    spoof = "test_spoof_" + uuid4().hex
    try:
        with admin.begin() as connection:
            connection.execute(CreateSchema(spoof))
            connection.execute(sa.text(f'CREATE TABLE "{spoof}".visits (id integer PRIMARY KEY)'))
            connection.execute(sa.text(f'INSERT INTO "{spoof}".visits VALUES (10)'))
            connection.execute(sa.text(f'CREATE FUNCTION "{spoof}".all_free_pending_exists(integer) RETURNS boolean LANGUAGE SQL AS $$ SELECT false $$'))
            connection.execute(sa.text(f'GRANT USAGE ON SCHEMA "{spoof}" TO "{runtime}"'))
            connection.execute(sa.text(f'GRANT SELECT, UPDATE ON "{spoof}".visits TO "{runtime}"'))
            connection.execute(sa.text(f'GRANT EXECUTE ON FUNCTION "{spoof}".all_free_pending_exists(integer) TO "{runtime}"'))
        with Session(engine) as db:
            _set_role(db, runtime)
            db.execute(sa.text(f'SET LOCAL search_path TO "{spoof}", "{schema}"'))
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(db, 10)
            assert error.value.status_code == 503
    finally:
        with admin.begin() as connection:
            connection.execute(DropSchema(spoof, cascade=True))


def test_untrusted_schema_create_privilege_fails_closed(capability):
    engine, admin, schema, _owner, runtime, outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT CREATE ON SCHEMA "{schema}" TO "{outsider}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


def test_public_function_execute_fails_closed(capability):
    engine, admin, schema, _owner, runtime, _outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT EXECUTE ON FUNCTION "{capability_schema_name(schema)}".all_free_pending_exists(integer) TO PUBLIC'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


@pytest.mark.parametrize("membership", ["other", "inherited"])
def test_membership_in_function_owner_fails_closed(capability, membership):
    engine, admin, _schema, owner, runtime, outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT "{owner}" TO "{outsider}"'))
        if membership == "inherited":
            connection.execute(sa.text(f'GRANT "{outsider}" TO "{runtime}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


@pytest.mark.parametrize("alteration", ["invoker", "search_path", "row_security"])
def test_altered_function_security_configuration_fails_closed(capability, alteration):
    engine, admin, schema, _owner, runtime, _outsider = capability
    changes = {
        "invoker": "SECURITY INVOKER",
        "search_path": "SET search_path = public",
        "row_security": "RESET row_security",
    }
    with admin.begin() as connection:
        connection.execute(sa.text(f'ALTER FUNCTION "{capability_schema_name(schema)}".all_free_pending_exists(integer) {changes[alteration]}'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


def test_function_owner_must_match_table_owner(capability):
    engine, admin, schema, _owner, runtime, outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT CREATE ON SCHEMA "{schema}" TO "{outsider}"'))
        connection.execute(sa.text(f'ALTER FUNCTION "{capability_schema_name(schema)}".all_free_pending_exists(integer) OWNER TO "{outsider}"'))
        connection.execute(sa.text(f'REVOKE CREATE ON SCHEMA "{schema}" FROM "{outsider}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


def test_login_function_owner_fails_closed(capability):
    engine, admin, _schema, owner, runtime, _outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'ALTER ROLE "{owner}" LOGIN'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


@pytest.mark.parametrize("attribute", ["CREATEROLE", "CREATEDB", "REPLICATION"])
@pytest.mark.parametrize("inherited", [False, True])
def test_administrative_runtime_capability_fails_closed(capability, attribute, inherited):
    engine, admin, _schema, _owner, runtime, outsider = capability
    with admin.begin() as connection:
        recipient = outsider if inherited else runtime
        connection.execute(sa.text(f'ALTER ROLE "{recipient}" {attribute}'))
        if inherited:
            connection.execute(sa.text(f'GRANT "{outsider}" TO "{runtime}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


def test_local_search_path_rollback_restores_safe_pooled_connection(capability):
    engine, _admin, _schema, _owner, runtime, _outsider = capability
    # Keep one physical connection checked out, then reuse it after rollback.
    with engine._guard_test_role_engines[runtime].connect() as connection:
        with Session(connection) as first:
            _set_role(first, runtime)
            first.execute(sa.text("SET LOCAL search_path TO pg_catalog"))
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(first, 11)
            assert error.value.status_code == 503
            first.rollback()
        with Session(connection) as second:
            _set_role(second, runtime)
            assert lock_visit_without_pending(second, 11) is None
            with pytest.raises(HTTPException) as error:
                lock_visit_without_pending(second, 10)
            assert error.value.status_code == 409
            second.rollback()


@pytest.mark.parametrize("via_membership", [False, True])
def test_runtime_raw_request_select_fails_closed(capability, via_membership):
    engine, admin, schema, _owner, runtime, outsider = capability
    with admin.begin() as connection:
        recipient = outsider if via_membership else runtime
        connection.execute(sa.text(f'GRANT SELECT ON "{schema}".all_free_requests TO "{recipient}"'))
        if via_membership:
            connection.execute(sa.text(f'GRANT "{outsider}" TO "{runtime}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


def test_disabling_request_table_rls_fails_closed(capability):
    engine, admin, schema, _owner, runtime, _outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'ALTER TABLE "{schema}".all_free_requests DISABLE ROW LEVEL SECURITY'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


@pytest.mark.parametrize("alteration", ["STABLE", "SET statement_timeout = '1min'"])
def test_function_volatility_and_extra_config_fails_closed(capability, alteration):
    engine, admin, schema, _owner, runtime, _outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'ALTER FUNCTION "{capability_schema_name(schema)}".all_free_pending_exists(integer) {alteration}'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


@pytest.mark.parametrize("privilege", ["SELECT (status)", "UPDATE (status)"])
def test_runtime_column_only_request_privilege_fails_closed(capability, privilege):
    engine, admin, schema, _owner, runtime, _outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT {privilege} ON "{schema}".all_free_requests TO "{runtime}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503


@pytest.mark.parametrize("privilege", ["INSERT", "UPDATE", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"])
def test_runtime_request_write_or_control_privilege_fails_closed(capability, privilege):
    engine, admin, schema, _owner, runtime, _outsider = capability
    with admin.begin() as connection:
        connection.execute(sa.text(f'GRANT {privilege} ON "{schema}".all_free_requests TO "{runtime}"'))
    with Session(engine) as db:
        _set_role(db, runtime)
        with pytest.raises(HTTPException) as error:
            lock_visit_without_pending(db, 11)
        assert error.value.status_code == 503

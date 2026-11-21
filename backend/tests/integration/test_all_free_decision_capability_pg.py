"""Synthetic PostgreSQL checks for the 0120 decision primitive.

This fixture is deliberately minimal and is not an Alembic-chain or financial
flow test. The backend role is a real LOGIN; no external service is called.
"""
from __future__ import annotations

import importlib.util
import os
import secrets
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.capability_namespace import capability_schema_name


@pytest.fixture
def decision_db():
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex
    schema, runtime, other = "allfree_" + suffix, "free_runtime_" + suffix, "free_other_" + suffix
    private = capability_schema_name(schema)
    admin = sa.create_engine(url, hide_parameters=True)
    runtime_engines = []
    roles = []
    with admin.begin() as db:
        db.execute(CreateSchema(schema))
    engine = sa.create_engine(url, hide_parameters=True, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000"})
    try:
        with engine.begin() as db:
            db.execute(sa.text(f'CREATE SCHEMA "{private}"'))
            db.execute(sa.text(f'REVOKE ALL ON SCHEMA "{private}" FROM PUBLIC'))
            db.execute(sa.text(f'''CREATE TABLE "{private}".clinic_capability_namespace (
                id smallint PRIMARY KEY, format_version smallint NOT NULL,
                application_schema text NOT NULL, private_schema text NOT NULL)'''))
            db.execute(sa.text(f'''CREATE TABLE "{private}".clinic_capability_role_profile (
                role_name text PRIMARY KEY, role_kind text NOT NULL)'''))
            db.execute(sa.text(f'''INSERT INTO "{private}".clinic_capability_namespace VALUES (1,1,:app,:private)'''),
                       {"app": schema, "private": private})
            db.execute(sa.text("CREATE TABLE users (id integer PRIMARY KEY, role text NOT NULL, is_active boolean, is_superuser boolean, auth_epoch bigint NOT NULL)"))
            db.execute(sa.text("CREATE TABLE patients (id integer PRIMARY KEY, is_deleted boolean)"))
            db.execute(sa.text("CREATE TABLE encounters (id integer PRIMARY KEY, patient_id integer, generation bigint)"))
            db.execute(sa.text("CREATE TABLE visits (id integer PRIMARY KEY, patient_id integer, encounter_id integer, confirmation_context_epoch bigint)"))
            db.execute(sa.text('''CREATE TABLE all_free_requests (
                id integer PRIMARY KEY, status text, visit_id integer, patient_id integer, encounter_id integer,
                visit_id_snapshot integer, patient_id_snapshot integer, encounter_id_snapshot integer,
                visit_context_epoch bigint, encounter_generation bigint, policy_auto_approve boolean,
                requested_by_user_id integer, decision_kind text, decision_context_epoch bigint,
                decided_by_user_id integer, decided_by_user_id_snapshot integer,
                decided_by_role_snapshot text, decided_at timestamptz)'''))
            db.execute(sa.text('''CREATE TABLE all_free_request_events (
                id serial PRIMARY KEY, request_id integer, event_type text, actor_user_id integer,
                actor_user_id_snapshot integer, actor_role_snapshot text)'''))
            db.execute(sa.text("INSERT INTO users VALUES (1,'Admin',true,false,3),(2,'Doctor',true,false,4),(3,'SuperAdmin',true,false,5)"))
            db.execute(sa.text("INSERT INTO patients VALUES (10,false)"))
            db.execute(sa.text("INSERT INTO encounters VALUES (20,10,7)"))
            db.execute(sa.text("INSERT INTO visits VALUES (30,10,20,9)"))
            db.execute(sa.text("INSERT INTO all_free_requests (id,status,visit_id,patient_id,encounter_id,visit_id_snapshot,patient_id_snapshot,encounter_id_snapshot,visit_context_epoch,encounter_generation,policy_auto_approve,requested_by_user_id) VALUES (40,'pending',30,10,20,30,10,20,8,7,true,2)"))
            path = Path(__file__).resolve().parents[2] / "alembic/versions/0120_all_free_decision_capability.py"
            spec = importlib.util.spec_from_file_location("synthetic_allfree_0120", path)
            assert spec and spec.loader
            migration = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(migration)
            assert migration._private_name(schema) == private
            with Operations.context(MigrationContext.configure(db, opts={"version_table_schema": schema})):
                migration.upgrade()
        with admin.begin() as db:
            for role in (runtime, other):
                password = secrets.token_urlsafe(24)
                statement = db.execute(sa.text("SELECT pg_catalog.format('CREATE ROLE %I LOGIN PASSWORD %L NOSUPERUSER NOBYPASSRLS', CAST(:role AS text), CAST(:password AS text))"),
                                       {"role": role, "password": password}).scalar_one()
                db.exec_driver_sql(statement)
                roles.append(role)
                runtime_engines.append(sa.create_engine(url.set(username=role, password=password), hide_parameters=True))
                db.exec_driver_sql(f'GRANT USAGE ON SCHEMA "{private}" TO "{role}"')
            db.exec_driver_sql(f'GRANT EXECUTE ON FUNCTION "{private}".decide_all_free(integer,text,text,integer,bigint,integer,integer,integer,bigint,bigint,bigint) TO "{runtime}"')
        yield engine, runtime_engines[0], runtime_engines[1], schema, private
    finally:
        for role_engine in runtime_engines:
            role_engine.dispose()
        engine.dispose()
        with admin.begin() as db:
            for role in reversed(roles):
                db.exec_driver_sql(f'DROP OWNED BY "{role}"')
                db.exec_driver_sql(f'DROP ROLE "{role}"')
            db.execute(DropSchema(private, cascade=True))
            db.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _call(db, private, *, action="approve", kind="admin", actor=1, epoch=3, visit=30, final_epoch=9):
    return db.execute(sa.text(f'''SELECT "{private}".decide_all_free(
        40,:action,:kind,:actor,:epoch,:visit,10,20,8,7,:final_epoch)'''),
        {"action": action, "kind": kind, "actor": actor, "epoch": epoch,
         "visit": visit, "final_epoch": final_epoch}).scalar_one()


@pytest.mark.parametrize("actor,epoch", [(1, 3), (3, 5)])
def test_admin_decision_is_atomic_and_not_replayable(decision_db, actor, epoch):
    engine, runtime, _, schema, private = decision_db
    with runtime.begin() as db:
        assert _call(db, private, actor=actor, epoch=epoch) > 0
    with runtime.connect() as db, pytest.raises(DBAPIError):
        _call(db, private, actor=actor, epoch=epoch)
    with engine.connect() as db:
        assert db.execute(sa.text(f'SELECT status FROM "{schema}".all_free_requests')).scalar_one() == "approved"
        assert db.execute(sa.text(f'SELECT count(*) FROM "{schema}".all_free_request_events')).scalar_one() == 1


@pytest.mark.parametrize("change", ["actor", "epoch", "visit", "final_epoch", "action", "kind"])
def test_invalid_decision_does_not_mutate(decision_db, change):
    engine, runtime, _, schema, private = decision_db
    args = {"actor": {"actor": 2, "epoch": 4}, "epoch": {"epoch": 4}, "visit": {"visit": 31},
            "final_epoch": {"final_epoch": 10}, "action": {"action": "other"},
            "kind": {"kind": "policy", "action": "reject"}}[change]
    with runtime.connect() as db, pytest.raises(DBAPIError):
        _call(db, private, **args)
    with engine.connect() as db:
        assert db.execute(sa.text(f'SELECT status FROM "{schema}".all_free_requests')).scalar_one() == "pending"
        assert db.execute(sa.text(f'SELECT count(*) FROM "{schema}".all_free_request_events')).scalar_one() == 0


def test_policy_requires_original_requester_and_rollback_is_atomic(decision_db):
    engine, runtime, _, schema, private = decision_db
    with runtime.connect() as db:
        tx = db.begin()
        assert _call(db, private, kind="policy", actor=2, epoch=4) > 0
        tx.rollback()
    with engine.connect() as db:
        assert db.execute(sa.text(f'SELECT status FROM "{schema}".all_free_requests')).scalar_one() == "pending"
        assert db.execute(sa.text(f'SELECT count(*) FROM "{schema}".all_free_request_events')).scalar_one() == 0
    with runtime.connect() as db, pytest.raises(DBAPIError):
        _call(db, private, kind="policy", actor=1, epoch=3)


def test_other_login_cannot_execute_or_update(decision_db):
    _, _, other, schema, private = decision_db
    with other.connect() as db, pytest.raises(DBAPIError):
        _call(db, private)
    with other.connect() as db, pytest.raises(DBAPIError):
        db.execute(sa.text(f'UPDATE "{schema}".all_free_requests SET status=\'approved\''))

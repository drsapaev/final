"""Synthetic PostgreSQL checks for persistent repeat-evidence allocation."""
from __future__ import annotations

import importlib.util
import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

FLOOR = 1 << 52


@pytest.fixture
def database():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    schema = "repeat_alloc_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as db:
        db.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema},pg_catalog"})
    try:
        with engine.begin() as db:
            db.execute(sa.text("CREATE TABLE users (id integer PRIMARY KEY)"))
            db.execute(sa.text("CREATE TABLE doctors (id integer PRIMARY KEY, user_id integer)"))
            db.execute(sa.text("CREATE TABLE visits (id integer PRIMARY KEY, patient_id integer, doctor_id integer, visit_date date, status text)"))
            db.execute(sa.text("CREATE TABLE visit_services (id integer PRIMARY KEY, visit_id integer, service_id integer, qty integer)"))
            db.execute(sa.text("INSERT INTO doctors VALUES (1,NULL)"))
            db.execute(sa.text("INSERT INTO visits VALUES (1,1,NULL,'2030-01-01','completed')"))
        yield engine, schema
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _revision(db, direction, schema):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0103_visit_consultation_completion.py"
    spec = importlib.util.spec_from_file_location("repeat_allocator_0103", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema}))
    getattr(module, direction)()


def test_rejects_preexisting_low_sequence(database):
    engine, schema = database
    with engine.begin() as db:
        db.execute(sa.text("CREATE SEQUENCE repeat_evidence_generation_seq START 1"))
    with engine.connect() as db, pytest.raises(RuntimeError, match="allocator sequence configuration"):
        with db.begin():
            _revision(db, "upgrade", schema)


def test_temporary_shadow_does_not_allocate_repeat_generations(database):
    engine, schema = database
    with engine.begin() as db:
        db.execute(sa.text("CREATE TEMP SEQUENCE repeat_evidence_generation_seq START 1"))
        _revision(db, "upgrade", schema)
        assert db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one() > FLOOR
        assert db.execute(sa.text("SELECT last_value FROM pg_temp.repeat_evidence_generation_seq")).scalar_one() == 1


def test_evidence_invalidates_context_and_keeps_price_only_correction(database):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        db.execute(sa.text("INSERT INTO users VALUES (1),(2)"))
        db.execute(sa.text("UPDATE doctors SET user_id=1 WHERE id=1"))
        db.execute(sa.text("INSERT INTO visits VALUES (2,1,1,'2030-01-02','open')"))
        db.execute(sa.text("INSERT INTO visit_services VALUES (1,2,10,1)"))
        before = db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=2")).scalar_one()
        db.execute(sa.text("UPDATE visits SET status='completed',repeat_proof_generation=:g,repeat_proof_consultation=true,repeat_proof_doctor_user_id=1 WHERE id=2"), {"g": before})
        db.execute(sa.text("UPDATE visit_services SET qty=qty WHERE id=1"))
        row = db.execute(sa.text("SELECT repeat_evidence_generation,repeat_proof_generation FROM visits WHERE id=2")).one()
        assert row == (before, before)
        db.execute(sa.text("UPDATE doctors SET user_id=2 WHERE id=1"))
        db.execute(sa.text("UPDATE doctors SET user_id=1 WHERE id=1"))
        assert db.execute(sa.text("SELECT repeat_proof_doctor_user_id FROM visits WHERE id=2")).scalar_one() == 1
        db.execute(sa.text("UPDATE visits SET visit_date='2030-01-03' WHERE id=2"))
        db.execute(sa.text("UPDATE visits SET visit_date='2030-01-02' WHERE id=2"))
        row = db.execute(sa.text("SELECT repeat_evidence_generation,repeat_proof_generation FROM visits WHERE id=2")).one()
        assert row[0] > before and row[1] is None


def test_doctor_reassignment_during_care_cannot_create_owner_provenance(database):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        db.execute(sa.text("INSERT INTO users VALUES (1),(2)"))
        db.execute(sa.text("UPDATE doctors SET user_id=1 WHERE id=1"))
        db.execute(sa.text("INSERT INTO doctors (id,user_id) VALUES (2,2)"))
        db.execute(sa.text("INSERT INTO visits (id,patient_id,doctor_id,visit_date,status) VALUES (2,1,1,'2030-01-02','in_progress'),(3,1,1,'2030-01-03','open')"))
        assert db.execute(sa.text("SELECT repeat_assigned_doctor_user_id FROM visits WHERE id=2")).scalar_one() is None
        db.execute(sa.text("UPDATE visits SET doctor_id=2 WHERE id IN (2,3)"))
        assert db.execute(sa.text("SELECT repeat_assigned_doctor_user_id FROM visits WHERE id=2")).scalar_one() is None
        assert db.execute(sa.text("SELECT repeat_assigned_doctor_user_id FROM visits WHERE id=3")).scalar_one() == 2
        db.execute(sa.text("UPDATE visits SET doctor_id=1 WHERE id=2"))
        assert db.execute(sa.text("SELECT repeat_assigned_doctor_user_id FROM visits WHERE id=2")).scalar_one() is None


def test_persistent_allocator_survives_downgrade_and_reupgrade(database):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        first = db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one()
        _revision(db, "downgrade", schema)
        _revision(db, "upgrade", schema)
        second = db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one()
        assert FLOOR < first < second


def test_downgrade_checks_real_evidence_despite_temp_shadow(database):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        db.execute(sa.text("UPDATE visits SET repeat_proof_generation=123 WHERE id=1"))
    with engine.connect() as db, pytest.raises(sa.exc.DBAPIError, match="evidence or assignments"):
        with db.begin():
            db.execute(sa.text("CREATE TEMP TABLE visits (repeat_proof_generation bigint, repeat_proof_consultation boolean, repeat_proof_doctor_user_id integer, repeat_assigned_owner_generation bigint, repeat_assigned_doctor_user_id integer)"))
            _revision(db, "downgrade", schema)
    with engine.connect() as db:
        assert db.execute(sa.text("SELECT repeat_proof_generation FROM visits WHERE id=1")).scalar_one() == 123


def test_downgrade_refuses_missing_persistent_sequence(database):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        db.execute(sa.text("DROP SEQUENCE repeat_evidence_generation_seq"))
    with engine.connect() as db, pytest.raises(RuntimeError, match="allocator sequence is missing"):
        with db.begin():
            _revision(db, "downgrade", schema)
    with engine.connect() as db:
        assert db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one() > FLOOR


def test_rejects_public_sequence_mutation_grant(database):
    engine, schema = database
    with engine.begin() as db:
        db.execute(sa.text("CREATE SEQUENCE repeat_evidence_generation_seq START 4503599627370497"))
        db.execute(sa.text("GRANT UPDATE ON SEQUENCE repeat_evidence_generation_seq TO PUBLIC"))
    with engine.connect() as db, pytest.raises(RuntimeError, match="allocator sequence configuration"):
        with db.begin():
            _revision(db, "upgrade", schema)


def test_reviewed_usage_only_runtime_survives_reupgrade(database, monkeypatch):
    engine, schema = database
    runtime = "repeat_runtime_" + uuid4().hex[:16]
    quote = engine.dialect.identifier_preparer.quote_identifier
    try:
        with engine.begin() as db:
            db.exec_driver_sql(f"CREATE ROLE {quote(runtime)} LOGIN NOSUPERUSER NOBYPASSRLS")
            _revision(db, "upgrade", schema)
            first = db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one()
            _revision(db, "downgrade", schema)
            db.exec_driver_sql(f"GRANT USAGE ON SEQUENCE {quote(schema)}.repeat_evidence_generation_seq TO {quote(runtime)}")
        monkeypatch.delenv("REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS", raising=False)
        with engine.connect() as db, pytest.raises(RuntimeError, match="allocator sequence configuration"):
            with db.begin():
                _revision(db, "upgrade", schema)
        monkeypatch.setenv("REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS", json.dumps([runtime]))
        with engine.begin() as db:
            _revision(db, "upgrade", schema)
            assert db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one() > first
            rights = db.execute(sa.text("""
              SELECT pg_catalog.has_sequence_privilege(:role, :seq, 'USAGE'),
                     pg_catalog.has_sequence_privilege(:role, :seq, 'UPDATE')
            """), {"role": runtime, "seq": f'{quote(schema)}.repeat_evidence_generation_seq'}).one()
            assert rights == (True, False)
    finally:
        with engine.begin() as db:
            db.exec_driver_sql(f"DROP OWNED BY {quote(runtime)}")
            db.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(runtime)}")


def test_rejects_unreviewed_schema_owner_member(database, monkeypatch):
    engine, schema = database
    member = "repeat_unreviewed_" + uuid4().hex[:16]
    quote = engine.dialect.identifier_preparer.quote_identifier
    monkeypatch.delenv("REPEAT_ALLOCATOR_TRUSTED_OWNER_MEMBERS", raising=False)
    try:
        with engine.begin() as db:
            owner = db.execute(sa.text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).scalar_one()
            db.exec_driver_sql(f"CREATE ROLE {quote(member)} NOLOGIN NOSUPERUSER")
            db.exec_driver_sql(f"GRANT {quote(owner)} TO {quote(member)}")
        with engine.connect() as db, pytest.raises(RuntimeError, match="allocator owner members"):
            with db.begin():
                _revision(db, "upgrade", schema)
    finally:
        with engine.begin() as db:
            db.exec_driver_sql(f"REVOKE {quote(owner)} FROM {quote(member)}")
            db.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(member)}")


def test_rejects_public_schema_create(database):
    engine, schema = database
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"GRANT CREATE ON SCHEMA {quote(schema)} TO PUBLIC")
    with engine.connect() as db, pytest.raises(RuntimeError, match="schema ownership"):
        with db.begin():
            _revision(db, "upgrade", schema)


def test_rejects_hostile_default_sequence_acl_before_allocating(database):
    engine, schema = database
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {quote(schema)} GRANT UPDATE ON SEQUENCES TO PUBLIC")
    try:
        with engine.connect() as db, pytest.raises(RuntimeError, match="allocator sequence configuration"):
            with db.begin():
                _revision(db, "upgrade", schema)
        with engine.connect() as db:
            assert db.execute(sa.text("SELECT pg_catalog.to_regclass(:seq)"),
                              {"seq": f'{quote(schema)}.repeat_evidence_generation_seq'}).scalar_one() is None
    finally:
        with engine.begin() as db:
            db.exec_driver_sql(f"ALTER DEFAULT PRIVILEGES IN SCHEMA {quote(schema)} REVOKE UPDATE ON SEQUENCES FROM PUBLIC")


@pytest.mark.parametrize("configured", [False, True])
def test_fresh_runtime_visit_dml_requires_explicit_sequence_usage(database, monkeypatch, configured):
    engine, schema = database
    runtime = "repeat_writer_" + uuid4().hex[:16]
    password = uuid4().hex + uuid4().hex
    quote = engine.dialect.identifier_preparer.quote_identifier
    login_engine = None
    try:
        with engine.begin() as db:
            db.exec_driver_sql(f"CREATE ROLE {quote(runtime)} LOGIN NOSUPERUSER NOBYPASSRLS")
            db.execute(sa.text("SELECT pg_catalog.set_config('test.runtime_password',:password,true)"), {"password": password})
            db.exec_driver_sql(f"DO $$ BEGIN EXECUTE pg_catalog.format('ALTER ROLE %%I PASSWORD %%L', '{runtime}', pg_catalog.current_setting('test.runtime_password')); END $$")
            db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {quote(schema)} TO {quote(runtime)}")
            db.exec_driver_sql(f"GRANT SELECT,INSERT,UPDATE ON {quote(schema)}.visits, {quote(schema)}.doctors, {quote(schema)}.visit_services TO {quote(runtime)}")
            db.exec_driver_sql(f"INSERT INTO {quote(schema)}.users VALUES (1)")
        if configured:
            monkeypatch.setenv("REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS", json.dumps([runtime]))
        else:
            monkeypatch.delenv("REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS", raising=False)
        with engine.begin() as db:
            _revision(db, "upgrade", schema)
        login_engine = sa.create_engine(engine.url.set(username=runtime, password=password), hide_parameters=True)
        if configured:
            with login_engine.begin() as db:
                assert db.execute(sa.text("SELECT current_user,session_user")).one() == (runtime, runtime)
                db.exec_driver_sql(f"INSERT INTO {quote(schema)}.doctors (id,user_id) VALUES (2,1)")
                db.exec_driver_sql(f"INSERT INTO {quote(schema)}.visits (id,patient_id,doctor_id,visit_date,status) VALUES (2,1,2,'2030-01-02','open')")
                assert db.execute(sa.text(f"SELECT repeat_evidence_generation FROM {quote(schema)}.visits WHERE id=2")).scalar_one() > FLOOR
                db.exec_driver_sql(f"INSERT INTO {quote(schema)}.visit_services VALUES (2,2,10,1)")
                db.exec_driver_sql(f"UPDATE {quote(schema)}.visits SET visit_date='2030-01-03' WHERE id=2")
                db.exec_driver_sql(f"UPDATE {quote(schema)}.doctors SET user_id=NULL WHERE id=2")
                assert db.execute(sa.text(f"SELECT repeat_assigned_doctor_user_id FROM {quote(schema)}.visits WHERE id=2")).scalar_one() is None
        else:
            with login_engine.connect() as db, pytest.raises(sa.exc.DBAPIError) as exc:
                with db.begin():
                    db.exec_driver_sql(f"INSERT INTO {quote(schema)}.visits (id,patient_id,doctor_id,visit_date,status) VALUES (2,1,NULL,'2030-01-02','completed')")
            assert getattr(exc.value.orig, "sqlstate", None) == "42501"
    finally:
        if login_engine is not None:
            login_engine.dispose()
        with engine.begin() as db:
            db.exec_driver_sql(f"DROP OWNED BY {quote(runtime)}")
            db.exec_driver_sql(f"DROP ROLE IF EXISTS {quote(runtime)}")


def test_nonowner_migration_operator_keeps_trusted_owner():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    suffix = uuid4().hex[:16]
    schema, owner, operator = "repeat_owner_" + suffix, "repeat_o_" + suffix, "repeat_m_" + suffix
    engine = sa.create_engine(url)
    password = uuid4().hex + uuid4().hex
    login_engine = None
    q = engine.dialect.identifier_preparer.quote_identifier
    try:
        with engine.begin() as db:
            db.exec_driver_sql(f"CREATE ROLE {q(owner)} NOLOGIN NOSUPERUSER NOBYPASSRLS")
            db.exec_driver_sql(f"CREATE ROLE {q(operator)} LOGIN NOSUPERUSER NOBYPASSRLS")
            db.execute(sa.text("SELECT pg_catalog.set_config('test.operator_password',:password,true)"), {"password": password})
            db.exec_driver_sql(f"DO $$ BEGIN EXECUTE pg_catalog.format('ALTER ROLE %%I PASSWORD %%L', '{operator}', pg_catalog.current_setting('test.operator_password')); END $$")
            db.exec_driver_sql(f"GRANT {q(owner)} TO {q(operator)}")
            db.exec_driver_sql(f"CREATE SCHEMA {q(schema)} AUTHORIZATION {q(owner)}")
            db.exec_driver_sql(f"SET LOCAL ROLE {q(owner)}")
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.users (id integer PRIMARY KEY)")
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.doctors (id integer PRIMARY KEY, user_id integer)")
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.visits (id integer PRIMARY KEY, patient_id integer, doctor_id integer, visit_date date, status text)")
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.visit_services (id integer PRIMARY KEY, visit_id integer, service_id integer, qty integer)")
            db.exec_driver_sql(f"INSERT INTO {q(schema)}.visits VALUES (1,1,NULL,'2030-01-01','completed')")
        login_engine = sa.create_engine(url.set(username=operator, password=password), hide_parameters=True)
        with login_engine.begin() as db:
            assert db.execute(sa.text("SELECT current_user,session_user")).one() == (operator, operator)
            _revision(db, "upgrade", schema)
            assert db.execute(sa.text(f"SELECT repeat_evidence_generation FROM {q(schema)}.visits")).scalar_one() > FLOOR
            actual_owner = db.execute(sa.text("""
                SELECT pg_catalog.pg_get_userbyid(c.relowner) FROM pg_catalog.pg_class c
                JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=:schema AND c.relname='repeat_evidence_generation_seq'
            """), {"schema": schema}).scalar_one()
            assert actual_owner == owner
    finally:
        if login_engine is not None:
            login_engine.dispose()
        with engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
            for role in (operator, owner):
                db.exec_driver_sql(f"DROP OWNED BY {q(role)}")
                db.exec_driver_sql(f"DROP ROLE IF EXISTS {q(role)}")
        engine.dispose()


def test_hostile_schema_identifier_is_quoted_without_literal_interpolation():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    schema = "repeat_\"_'_\\_" + uuid4().hex[:12]
    engine = sa.create_engine(url)
    q = engine.dialect.identifier_preparer.quote_identifier
    try:
        with engine.begin() as db:
            db.execute(CreateSchema(schema))
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.users (id integer PRIMARY KEY)")
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.doctors (id integer PRIMARY KEY, user_id integer)")
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.visits (id integer PRIMARY KEY, patient_id integer, doctor_id integer, visit_date date, status text)")
            db.exec_driver_sql(f"CREATE TABLE {q(schema)}.visit_services (id integer PRIMARY KEY, visit_id integer, service_id integer, qty integer)")
            db.exec_driver_sql(f"INSERT INTO {q(schema)}.visits VALUES (1,1,NULL,'2030-01-01','completed')")
            db.execute(sa.text("SET LOCAL standard_conforming_strings=off"))
            _revision(db, "upgrade", schema)
            assert db.execute(sa.text(f"SELECT repeat_evidence_generation FROM {q(schema)}.visits")).scalar_one() > FLOOR
    finally:
        with engine.begin() as db:
            db.execute(DropSchema(schema, cascade=True, if_exists=True))
        engine.dispose()

"""Provision a repeat allocator for a separate synthetic PostgreSQL login."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError

from tests.integration.test_repeat_allocator_security_pg import _revision, database  # noqa: F401

_script_path = Path(__file__).resolve().parents[3] / "scripts/provision_repeat_allocator_role.py"
_spec = importlib.util.spec_from_file_location("repeat_allocator_provisioner", _script_path)
assert _spec and _spec.loader
_script = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_script)
ProvisionError, provision = _script.ProvisionError, _script.provision


def _runtime(engine, schema):
    role = "synthetic_repeat_runtime_" + uuid4().hex[:12]
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"CREATE ROLE {quote(role)} LOGIN PASSWORD 'synthetic-only-password' NOSUPERUSER NOBYPASSRLS")
        db.exec_driver_sql(f"GRANT USAGE ON SCHEMA {quote(schema)} TO {quote(role)}")
        db.exec_driver_sql(f"GRANT SELECT, INSERT ON {quote(schema)}.visits TO {quote(role)}")
        db.exec_driver_sql(f"GRANT SELECT ON {quote(schema)}.doctors TO {quote(role)}")
    return role


def _drop_role(engine, role):
    quote = engine.dialect.identifier_preparer.quote_identifier
    with engine.begin() as db:
        db.exec_driver_sql(f"DROP OWNED BY {quote(role)}")
        db.exec_driver_sql(f"DROP ROLE {quote(role)}")


def test_physical_runtime_needs_then_receives_only_usage(database):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).scalar_one()
        before = db.execute(text(f'SELECT last_value FROM "{schema}".repeat_evidence_generation_seq')).scalar_one()
    role = _runtime(engine, schema)
    runtime = create_engine(engine.url.set(username=role, password="synthetic-only-password"),
                            connect_args={"options": f"-csearch_path={schema},pg_catalog"})
    try:
        with runtime.connect() as db:
            with pytest.raises(DBAPIError):
                db.execute(text("INSERT INTO visits (id,patient_id,doctor_id,visit_date,status) VALUES (2,1,NULL,'2030-01-01','open')"))
            db.rollback()
        provision(engine, schema=schema, expected_owner=owner, runtime_roles=(role,))
        # Repeated provisioning is safe and never resets the counter.
        provision(engine, schema=schema, expected_owner=owner, runtime_roles=(role,))
        with engine.begin() as db:
            assert db.execute(text(f'SELECT last_value FROM "{schema}".repeat_evidence_generation_seq')).scalar_one() == before
            rights = db.execute(text("""
                SELECT pg_catalog.has_sequence_privilege(:role,:seq,'USAGE'),
                       pg_catalog.has_sequence_privilege(:role,:seq,'SELECT'),
                       pg_catalog.has_sequence_privilege(:role,:seq,'UPDATE')
            """), {"role": role, "seq": f'"{schema}".repeat_evidence_generation_seq'}).one()
            assert rights == (True, False, False)
        with runtime.connect() as db:
            with pytest.raises(DBAPIError) as error:
                db.execute(text("SELECT pg_catalog.setval('repeat_evidence_generation_seq',1)"))
            assert (getattr(error.value.orig, "sqlstate", None) or getattr(error.value.orig, "pgcode", None)) == "42501"
            db.rollback()
        with runtime.begin() as db:
            db.execute(text("INSERT INTO visits (id,patient_id,doctor_id,visit_date,status) VALUES (2,1,NULL,'2030-01-01','open')"))
        with engine.begin() as db:
            assert db.execute(text("SELECT repeat_evidence_generation FROM visits WHERE id=2")).scalar_one() > before
    finally:
        runtime.dispose()
        _drop_role(engine, role)


def test_unexpected_grant_and_wrong_owner_leave_role_unmodified(database):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).scalar_one()
    first, second = _runtime(engine, schema), _runtime(engine, schema)
    q = engine.dialect.identifier_preparer.quote_identifier
    try:
        with pytest.raises(ProvisionError, match="owner"):
            provision(engine, schema=schema, expected_owner="wrong_owner", runtime_roles=(first,))
        with engine.begin() as db:
            db.exec_driver_sql(f"GRANT UPDATE ON SEQUENCE {q(schema)}.repeat_evidence_generation_seq TO {q(second)}")
        with pytest.raises(RuntimeError, match="unsafe"):
            provision(engine, schema=schema, expected_owner=owner, runtime_roles=(first, second))
        with engine.begin() as db:
            assert not db.execute(text("SELECT pg_catalog.has_sequence_privilege(:role,:seq,'USAGE')"),
                                  {"role": first, "seq": f'"{schema}".repeat_evidence_generation_seq'}).scalar_one()
    finally:
        _drop_role(engine, first)
        _drop_role(engine, second)


def test_provisioned_allocator_survives_downgrade_reupgrade(database, monkeypatch):
    engine, schema = database
    with engine.begin() as db:
        _revision(db, "upgrade", schema)
        owner = db.execute(text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).scalar_one()
    role = _runtime(engine, schema)
    try:
        provision(engine, schema=schema, expected_owner=owner, runtime_roles=(role,))
        monkeypatch.setenv("REPEAT_ALLOCATOR_TRUSTED_SEQUENCE_USERS", json.dumps([role]))
        with engine.begin() as db:
            before = db.execute(text("SELECT last_value FROM repeat_evidence_generation_seq")).scalar_one()
            _revision(db, "downgrade", schema)
        with engine.begin() as db:
            _revision(db, "upgrade", schema)
            after = db.execute(text("SELECT last_value FROM repeat_evidence_generation_seq")).scalar_one()
            assert after > before
            assert db.execute(text("SELECT pg_catalog.has_sequence_privilege(:role,:seq,'USAGE')"),
                              {"role": role, "seq": f'"{schema}".repeat_evidence_generation_seq'}).scalar_one()
            assert not db.execute(text("SELECT pg_catalog.has_sequence_privilege(:role,:seq,'UPDATE')"),
                                  {"role": role, "seq": f'"{schema}".repeat_evidence_generation_seq'}).scalar_one()
    finally:
        _drop_role(engine, role)


def test_changed_migration_source_fails_before_loading(monkeypatch):
    monkeypatch.setattr(_script, "MIGRATION_SHA256", "0" * 64)
    with pytest.raises(ProvisionError, match="changed"):
        _script._migration()

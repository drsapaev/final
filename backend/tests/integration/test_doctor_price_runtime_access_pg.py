"""Synthetic 0121 RLS provisioning, with a real NOBYPASSRLS LOGIN role.

Uses a synthetic predecessor through real 0112, then applies 0121 directly;
this is not a complete Alembic-chain or production provisioning test.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations
from pydantic import SecretStr
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.capability_namespace import capability_schema_name

_ROOT = Path(__file__).resolve().parents[2]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def provisioned_pg():
    url = make_url(os.getenv("DOCTOR_PRICE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable PostgreSQL")
    schema = "test_price_access_" + uuid4().hex
    role = "test_price_login_" + uuid4().hex
    admin = sa.create_engine(url)
    quote = admin.dialect.identifier_preparer.quote_identifier
    with admin.begin() as db:
        db.execute(CreateSchema(schema))
        db.exec_driver_sql(f"CREATE ROLE {quote(role)} LOGIN NOBYPASSRLS NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION")
        owner = db.execute(sa.text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).scalar_one()
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    predecessor = _module("price_access_predecessor", Path(__file__).with_name("test_doctor_price_context_migration.py"))
    migration = _module("price_access_0121", _ROOT / "alembic/versions/0121_doctor_price_runtime_access.py")
    script = _module("price_access_provision", _ROOT.parent / "scripts/provision_doctor_price_backend_role.py")
    try:
        with engine.begin() as db:
            predecessor._predecessor(db)
            predecessor._migrate(db, "upgrade")
            migration.op = Operations(MigrationContext.configure(db, opts={"version_table_schema": schema}))
            migration.upgrade()
            for table in migration._TABLES:
                db.exec_driver_sql(f'ALTER TABLE {quote(schema)}.{quote(table)} FORCE ROW LEVEL SECURITY')
        script.provision(engine, schema, role)
        yield engine, schema, owner, role, script
    finally:
        engine.dispose()
        with admin.begin() as db:
            db.execute(DropSchema(schema, cascade=True))
            db.execute(DropSchema(capability_schema_name(schema), cascade=True, if_exists=True))
            db.exec_driver_sql(f'DROP OWNED BY {quote(role)}')
            db.exec_driver_sql(f'DROP ROLE {quote(role)}')
        admin.dispose()


def _keyring():
    from app.services.doctor_price_intent_service import PriceIntentKeyring
    return PriceIntentKeyring.from_settings(SimpleNamespace(
        DOCTOR_PRICE_HMAC_KEYS=SecretStr(json.dumps({"1": base64.urlsafe_b64encode(b"k" * 32).decode()})),
        DOCTOR_PRICE_HMAC_ACTIVE_VERSION=1,
    ))


def _runtime(db, schema, owner, role):
    from app.services.doctor_price_intent_service import DoctorPriceIntentService
    quoted = db.get_bind().dialect.identifier_preparer.quote_identifier(role)
    db.execute(sa.text(f"SET LOCAL SESSION AUTHORIZATION {quoted}"))
    service = DoctorPriceIntentService(db, _keyring(), schema, owner, role)
    service.pin_trusted_schema()
    service.lock_actor_scope(1, "schedule_next")
    service.verify_registry(register_active=True)
    return service


def test_runtime_login_can_use_registry_and_intents_even_under_forced_rls(provisioned_pg):
    engine, schema, owner, role, _ = provisioned_pg
    with Session(engine) as db:
        service = _runtime(db, schema, owner, role)
        version, digest = service.fingerprint({"patient_id": 1, "raw": 0})
        db.execute(sa.text("""
            INSERT INTO doctor_price_intents
              (operation,requester_type,actor_user_id,actor_user_id_snapshot,actor_user_auth_epoch,
               doctor_id,doctor_id_snapshot,doctor_owner_user_id,doctor_owner_user_id_snapshot,
               patient_id,patient_id_snapshot,visit_id,visit_id_snapshot,
               doctor_user_auth_epoch,price_owner_generation,fingerprint_version,fingerprint)
            VALUES ('schedule_next','doctor',1,1,0,10,10,1,1,1,1,1,1,0,1,:version,:digest)
        """), {"version": version, "digest": digest})
        intent_id = db.execute(sa.text("SELECT id FROM doctor_price_intents")).scalar_one()
        service.bind_alias(1, "schedule_next", intent_id, "test-opaque-key")
        assert service.lookup(1, "schedule_next", {"patient_id": 1, "raw": 0}, "test-opaque-key").intent_id == intent_id
        db.commit()
    with engine.connect() as db:
        assert db.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intents")).scalar_one() == 1


@pytest.mark.parametrize("tamper", ["extra_policy", "restrictive_policy", "update_grant", "revoke_select", "sequence_update"])
def test_runtime_refuses_partial_visibility_or_excess_privilege(provisioned_pg, tamper):
    from app.services.doctor_price_intent_service import PriceIntentUnavailable
    engine, schema, owner, role, _ = provisioned_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    table = f'{quote(schema)}.doctor_price_intents'
    with engine.begin() as db:
        if tamper == "extra_policy":
            db.exec_driver_sql(f'CREATE POLICY unexpected_price_policy ON {table} FOR SELECT TO {quote(role)} USING (true)')
        elif tamper == "restrictive_policy":
            db.exec_driver_sql(f'CREATE POLICY unexpected_price_policy ON {table} AS RESTRICTIVE FOR SELECT TO {quote(role)} USING (false)')
        elif tamper == "update_grant":
            db.exec_driver_sql(f'GRANT UPDATE ON {table} TO {quote(role)}')
        elif tamper == "revoke_select":
            db.exec_driver_sql(f'REVOKE SELECT ON {table} FROM {quote(role)}')
        else:
            seq = db.execute(sa.text("SELECT pg_catalog.pg_get_serial_sequence(:table,'id')"), {"table": table}).scalar_one()
            db.exec_driver_sql(f'GRANT UPDATE ON SEQUENCE {seq} TO {quote(role)}')
    with Session(engine) as db:
        with pytest.raises((PriceIntentUnavailable, sa.exc.DBAPIError)):
            _runtime(db, schema, owner, role)


def test_provision_is_repeatable_and_rejects_elevated_or_unexpected_policy(provisioned_pg):
    engine, schema, _, role, script = provisioned_pg
    script.provision(engine, schema, role)
    quoted = engine.dialect.identifier_preparer.quote_identifier(schema)
    with engine.begin() as db:
        db.exec_driver_sql(f'CREATE POLICY unexpected_policy ON {quoted}.doctor_price_intents FOR SELECT USING (true)')
    with pytest.raises(script.ProvisionError):
        script.provision(engine, schema, role)


def test_runtime_places_temp_schema_last_even_when_attacker_created_shadows(provisioned_pg):
    engine, schema, owner, role, _ = provisioned_pg
    quote = engine.dialect.identifier_preparer.quote_identifier
    with Session(engine) as db:
        db.execute(sa.text(f"SET LOCAL SESSION AUTHORIZATION {quote(role)}"))
        db.execute(sa.text("CREATE TEMP TABLE doctor_price_hmac_key_versions (version INTEGER, key_check_digest TEXT)"))
        db.execute(sa.text("CREATE TEMP TABLE doctor_price_intents (fingerprint_version INTEGER, issued_confirmation_digest_version INTEGER)"))
        from app.services.doctor_price_intent_service import DoctorPriceIntentService
        service = DoctorPriceIntentService(db, _keyring(), schema, owner, role)
        service.pin_trusted_schema()
        path = db.execute(sa.text("SELECT current_schemas(false)")).scalar_one()
        assert path[0:2] == ["pg_catalog", schema] and path[-1].startswith("pg_temp_")
        service.lock_actor_scope(1, "schedule_next")
        service.verify_registry(register_active=True)
        assert db.execute(sa.text("SELECT count(*) FROM doctor_price_hmac_key_versions")).scalar_one() == 1
        assert db.execute(sa.text("SELECT count(*) FROM pg_temp.doctor_price_hmac_key_versions")).scalar_one() == 0
        db.rollback()

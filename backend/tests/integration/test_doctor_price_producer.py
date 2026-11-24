"""Synthetic intent service tests, without notifications or provider calls.

The database has a synthetic predecessor plus actual 0102/0103/0112 migrations;
these tests do not substitute for authorization or financial integration.
"""
from __future__ import annotations

import base64
import importlib.util
import json
import os
import subprocess
import sys
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest
import sqlalchemy as sa
from pydantic import SecretStr
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.capability_namespace import capability_schema_name

_ROOT = Path(__file__).resolve().parents[2]


def _migration_test_module():
    path = Path(__file__).with_name("test_doctor_price_context_migration.py")
    spec = importlib.util.spec_from_file_location("synthetic_price_context_fixture", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'producer.sqlite'}")

    @sa.event.listens_for(engine, "connect")
    def configure(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
        connection.execute("PRAGMA busy_timeout=10000")

    migrations = _migration_test_module()
    try:
        with engine.begin() as connection:
            migrations._predecessor(connection)
            migrations._migrate(connection, "upgrade")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("DOCTOR_PRICE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable PostgreSQL clinic_test database")
    schema = "test_price_producer_" + uuid4().hex
    role = "test_price_login_" + uuid4().hex
    admin = sa.create_engine(url)
    quote = admin.dialect.identifier_preparer.quote_identifier
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
        connection.exec_driver_sql(f"CREATE ROLE {quote(role)} LOGIN NOBYPASSRLS NOSUPERUSER NOINHERIT NOCREATEDB NOCREATEROLE NOREPLICATION")
        owner = connection.execute(sa.text("SELECT pg_catalog.pg_get_userbyid(nspowner) FROM pg_catalog.pg_namespace WHERE nspname=:schema"), {"schema": schema}).scalar_one()
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    engine._doctor_price_test_schema = schema
    engine._doctor_price_test_owner = owner
    engine._doctor_price_test_role = role
    migrations = _migration_test_module()
    try:
        with engine.begin() as connection:
            migrations._predecessor(connection)
            migrations._migrate(connection, "upgrade")
            migration = migrations._module("test_price_access_0121", _ROOT / "alembic/versions/0121_doctor_price_runtime_access.py")
            migration.op = migrations.Operations(migrations.MigrationContext.configure(connection, opts={"version_table_schema": schema}))
            migration.upgrade()
            connection.exec_driver_sql(f"GRANT SELECT, UPDATE ON {quote(schema)}.users TO {quote(role)}")
        provision = migrations._module("test_price_access_provision", _ROOT.parent / "scripts/provision_doctor_price_backend_role.py")
        provision.provision(engine, schema, role)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
            connection.execute(DropSchema(capability_schema_name(schema), cascade=True, if_exists=True))
            connection.exec_driver_sql(f"DROP OWNED BY {quote(role)}")
            connection.exec_driver_sql(f"DROP ROLE {quote(role)}")
        admin.dispose()


def _engine(kind, request):
    return request.getfixturevalue("sqlite_engine" if kind == "sqlite" else "pg_engine")


def _keyring(active=1, versions=(1,)):
    from app.services.doctor_price_intent_service import PriceIntentKeyring

    keys = {str(version): base64.urlsafe_b64encode(bytes([version]) * 32).decode("ascii") for version in versions}
    return PriceIntentKeyring.from_settings(SimpleNamespace(
        DOCTOR_PRICE_HMAC_KEYS=SecretStr(json.dumps(keys)),
        DOCTOR_PRICE_HMAC_ACTIVE_VERSION=active,
    ))


def _new_service(db, keyring):
    from app.services.doctor_price_intent_service import DoctorPriceIntentService

    engine = db.get_bind()
    role = getattr(engine, "_doctor_price_test_role", None)
    if role:
        current = db.execute(sa.text("SELECT current_user")).scalar_one()
        owner = getattr(engine, "_doctor_price_test_owner", None)
        if current == owner:
            quoted = engine.dialect.identifier_preparer.quote_identifier(role)
            db.execute(sa.text(f"SET LOCAL SESSION AUTHORIZATION {quoted}"))
    return DoctorPriceIntentService(db, keyring, getattr(engine, "_doctor_price_test_schema", None),
                                    getattr(engine, "_doctor_price_test_owner", None), role)


def _service(db, keyring, actor=1, operation="schedule_next"):
    service = _new_service(db, keyring)
    service.reserve_sqlite_writer()
    service.pin_trusted_schema()
    # Production caller locks/rechecks all relevant User rows here before the
    # advisory scope and later clinical reads. Fixture actors are synthetic.
    db.execute(sa.text("SELECT id FROM users WHERE id=:id FOR UPDATE" if db.get_bind().dialect.name == "postgresql" else "SELECT id FROM users WHERE id=:id"), {"id": actor})
    service.lock_actor_scope(actor, operation)
    service.verify_registry(register_active=True)
    return service


def _payload(raw_price=None):
    return {"actor_id": 1, "operation": "schedule_next", "patient_id": 1,
            "visit_date": "2031-04-01", "services": [{"service_id": 9, "quantity": 1,
            "custom_price_minor": raw_price}], "notes": "synthetic"}


def _insert_intent(db, service, payload, ident=1):
    version, fingerprint = service.fingerprint(payload)
    db.execute(sa.text("""
        INSERT INTO doctor_price_intents
          (id,operation,requester_type,actor_user_id,actor_user_id_snapshot,actor_user_auth_epoch,
           doctor_id,doctor_id_snapshot,doctor_owner_user_id,doctor_owner_user_id_snapshot,
           patient_id,patient_id_snapshot,visit_id,visit_id_snapshot,
           doctor_user_auth_epoch,price_owner_generation,fingerprint_version,fingerprint)
        VALUES (:id,'schedule_next','doctor',1,1,0,10,10,1,1,1,1,1,1,0,1,:version,:fingerprint)
    """), {"id": ident, "version": version, "fingerprint": fingerprint})


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_legacy_no_key_retry_finds_previously_committed_intent_and_binds_multiple_aliases(kind, request):
    engine = _engine(kind, request)
    with Session(engine) as db:
        service = _service(db, _keyring())
        _insert_intent(db, service, _payload())
        db.commit()
    for key in ("key-one", "key-two"):
        with Session(engine) as db:
            service = _service(db, _keyring())
            result = service.lookup(1, "schedule_next", _payload(), key, datetime.now(UTC), mode="retry")
            assert result.intent_id == 1 and result.needs_alias
            assert db.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intent_keys WHERE intent_id=1")).scalar_one() == (0 if key == "key-one" else 1)
            # Endpoint reauthorizes and revalidates before calling this method.
            service.bind_alias(1, "schedule_next", 1, key)
            db.commit()
    with Session(engine) as db:
        service = _service(db, _keyring())
        result = service.lookup(1, "schedule_next", _payload(), "key-one", datetime.now(UTC))
        assert result.intent_id == 1 and not result.needs_alias
        from app.services.doctor_price_intent_service import PriceIntentConflict
        with pytest.raises(PriceIntentConflict):
            service.lookup(1, "schedule_next", _payload(0), "key-one", datetime.now(UTC))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_rotation_checks_old_version_and_compares_original_fingerprint(kind, request):
    engine = _engine(kind, request)
    with Session(engine) as db:
        service = _service(db, _keyring(active=1, versions=(1, 2)))
        _insert_intent(db, service, _payload())
        db.commit()
    with Session(engine) as db:
        service = _service(db, _keyring(active=2, versions=(1, 2)))
        result = service.lookup(1, "schedule_next", _payload(), "new-key", datetime.now(UTC), mode="retry")
        assert result.intent_id == 1 and result.needs_alias
        assert service.lookup(1, "schedule_next", _payload(0), None, datetime.now(UTC)).intent_id is None
        db.commit()
    from app.services.doctor_price_intent_service import PriceIntentUnavailable
    with Session(engine) as db:
        with pytest.raises(PriceIntentUnavailable):
            _service(db, _keyring(active=2, versions=(2,)))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_read_only_check_rejects_unregistered_active_without_writing(kind, request):
    from app.services.doctor_price_intent_service import PriceIntentUnavailable
    engine = _engine(kind, request)
    with Session(engine) as db:
        service = _new_service(db, _keyring())
        with pytest.raises(PriceIntentUnavailable):
            service.verify_registry(register_active=False)
        assert db.execute(sa.text("SELECT COUNT(*) FROM doctor_price_hmac_key_versions")).scalar_one() == 0


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_recent_lookup_does_not_depend_on_mutable_visit(kind, request):
    engine = _engine(kind, request)
    with Session(engine) as db:
        service = _service(db, _keyring())
        _insert_intent(db, service, _payload())
        db.commit()
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE visits SET patient_id=2 WHERE id=1"))
    with Session(engine) as db:
        service = _service(db, _keyring())
        from app.services.doctor_price_intent_service import PriceIntentAmbiguous
        with pytest.raises(PriceIntentAmbiguous):
            service.lookup(1, "schedule_next", _payload(), None, datetime.now(UTC))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_recent_multiple_matches_are_ambiguous_not_arbitrary(kind, request):
    from app.services.doctor_price_intent_service import PriceIntentConflict
    with Session(_engine(kind, request)) as db:
        service = _service(db, _keyring())
        _insert_intent(db, service, _payload(), ident=1)
        _insert_intent(db, service, _payload(), ident=2)
        with pytest.raises(PriceIntentConflict):
            service.lookup(1, "schedule_next", _payload(), None, datetime.now(UTC))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_unused_historical_secret_can_be_removed_but_commitment_cannot_change(kind, request):
    from app.services.doctor_price_intent_service import PriceIntentUnavailable
    engine = _engine(kind, request)
    with Session(engine) as db:
        _service(db, _keyring(active=1, versions=(1,)))
        db.commit()
    with Session(engine) as db:
        _service(db, _keyring(active=2, versions=(2,)))
        db.commit()
    wrong = SimpleNamespace(
        DOCTOR_PRICE_HMAC_ACTIVE_VERSION=1,
        DOCTOR_PRICE_HMAC_KEYS=SecretStr(json.dumps({"1": base64.urlsafe_b64encode(b"x" * 32).decode("ascii")})),
    )
    from app.services.doctor_price_intent_service import PriceIntentKeyring
    with Session(engine) as db:
        with pytest.raises(PriceIntentUnavailable):
            _service(db, PriceIntentKeyring.from_settings(wrong))


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_concurrent_same_actor_no_key_is_created_once_or_ambiguous(kind, request):
    from app.services.doctor_price_intent_service import (
        PriceIntentAmbiguous,
        PriceIntentRetryable,
    )
    engine = _engine(kind, request)
    barrier = threading.Barrier(2)

    def worker(_):
        try:
            with Session(engine) as db:
                barrier.wait(timeout=10)
                service = _service(db, _keyring())
                try:
                    result = service.lookup(1, "schedule_next", _payload(), None, datetime.now(UTC))
                except PriceIntentAmbiguous:
                    return "ambiguous"
                assert result.intent_id is None
                _insert_intent(db, service, _payload())
                db.commit()
                return "created"
        except PriceIntentRetryable:
            return "pending"

    with ThreadPoolExecutor(max_workers=2) as executor:
        outcomes = list(executor.map(worker, (1, 2)))
    assert outcomes.count("created") == 1
    assert set(outcomes) <= {"created", "ambiguous", "pending"}
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intents")).scalar_one() == 1


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_fingerprint_rejects_float_and_does_not_confuse_none_zero(kind, request):
    from app.services.doctor_price_intent_service import PriceIntentInvalid
    with Session(_engine(kind, request)) as db:
        service = _service(db, _keyring())
        assert service.fingerprint(_payload())[1] != service.fingerprint(_payload(0))[1]
        assert service.confirmation_digest("synthetic-token")[1] != service.fingerprint("synthetic-token")[1]
        for value in (1.0, float("nan"), Decimal("1.00"), {1: "invalid"}, object()):
            with pytest.raises(PriceIntentInvalid):
                service.fingerprint(value)


def test_invalid_keyrings_fail_without_exposing_key_material(caplog):
    from app.services.doctor_price_intent_service import (
        PriceIntentKeyring,
        PriceIntentUnavailable,
    )
    bad = [None, "{}", '{"1":"secret","1":"other"}',
           json.dumps({"01": base64.urlsafe_b64encode(b"x" * 32).decode("ascii")}),
           json.dumps({"1": base64.urlsafe_b64encode(b"x" * 16).decode("ascii")})]
    for raw in bad:
        with pytest.raises(PriceIntentUnavailable) as exc:
            PriceIntentKeyring.from_settings(SimpleNamespace(
                DOCTOR_PRICE_HMAC_KEYS=SecretStr(raw) if raw is not None else None,
                DOCTOR_PRICE_HMAC_ACTIVE_VERSION=1,
            ))
        assert "secret" not in str(exc.value)
    assert "secret" not in caplog.text


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_keyed_replay_and_unkeyed_ambiguity_do_not_depend_on_wall_clock(kind, request):
    engine = _engine(kind, request)
    with Session(engine) as db:
        service = _service(db, _keyring())
        _insert_intent(db, service, _payload())
        service.bind_alias(1, "schedule_next", 1, "retained-key")
        db.commit()
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE doctor_price_intents SET created_at='2001-01-01 00:00:00' WHERE id=1"))
    with Session(engine) as db:
        service = _service(db, _keyring())
        assert service.lookup(1, "schedule_next", _payload(), "retained-key", datetime.now(UTC)).intent_id == 1
        from app.services.doctor_price_intent_service import PriceIntentAmbiguous
        with pytest.raises(PriceIntentAmbiguous):
            service.lookup(1, "schedule_next", _payload(), None, datetime.now(UTC))


def test_postgres_filtered_registry_visibility_fails_closed(pg_engine):
    from app.services.doctor_price_intent_service import PriceIntentUnavailable
    role = "test_price_reader_" + uuid4().hex
    role_q = pg_engine.dialect.identifier_preparer.quote(role)
    with Session(pg_engine) as db:
        service = _service(db, _keyring())
        _insert_intent(db, service, _payload())
        db.commit()
    with pg_engine.begin() as connection:
        can_create = connection.execute(sa.text("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname=current_user")).scalar_one()
        if not can_create:
            pytest.skip("requires disposable PostgreSQL role creation privileges")
        schema = connection.execute(sa.text("SELECT current_schema()")).scalar_one()
        schema_q = connection.dialect.identifier_preparer.quote(schema)
        connection.exec_driver_sql(f"CREATE ROLE {role_q} NOLOGIN NOBYPASSRLS")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema_q} TO {role_q}")
        connection.exec_driver_sql(f"GRANT SELECT ON {schema_q}.doctor_price_hmac_key_versions, {schema_q}.doctor_price_intents TO {role_q}")
    try:
        with Session(pg_engine) as db:
            db.execute(sa.text(f"SET LOCAL ROLE {role_q}"))
            with pytest.raises(PriceIntentUnavailable):
                _new_service(db, _keyring()).verify_registry(register_active=False)
    finally:
        with pg_engine.begin() as connection:
            connection.exec_driver_sql(f"DROP OWNED BY {role_q}")
            connection.exec_driver_sql(f"DROP ROLE {role_q}")


def test_postgres_uses_explicit_trusted_schema_despite_shadow_search_path(pg_engine):
    from app.services.doctor_price_intent_service import (
        DoctorPriceIntentService,
        PriceIntentUnavailable,
    )
    shadow = "test_price_shadow_" + uuid4().hex
    with Session(pg_engine) as db:
        _service(db, _keyring())
        db.commit()
    with pg_engine.begin() as connection:
        connection.execute(CreateSchema(shadow))
    try:
        with Session(pg_engine) as db:
            quoted = pg_engine.dialect.identifier_preparer.quote_schema(shadow)
            db.execute(sa.text(f"SET LOCAL search_path TO {quoted}, pg_catalog"))
            service = _new_service(db, _keyring())
            service.pin_trusted_schema()
            path = db.execute(sa.text("SELECT current_schemas(false)")).scalar_one()
            assert path[:2] == ["pg_catalog", pg_engine._doctor_price_test_schema]
            service.verify_registry(register_active=False)
        with Session(pg_engine) as db:
            with pytest.raises(PriceIntentUnavailable):
                DoctorPriceIntentService(db, _keyring(), pg_engine._doctor_price_test_schema, "wrong-owner").pin_trusted_schema()
        with Session(pg_engine) as db:
            with pytest.raises(PriceIntentUnavailable):
                DoctorPriceIntentService(db, _keyring()).pin_trusted_schema()
    finally:
        with pg_engine.begin() as connection:
            connection.execute(DropSchema(shadow, cascade=True))


def test_postgres_writable_trusted_schema_is_refused(pg_engine):
    from app.services.doctor_price_intent_service import PriceIntentUnavailable
    quoted = pg_engine.dialect.identifier_preparer.quote_schema(pg_engine._doctor_price_test_schema)
    with pg_engine.begin() as connection:
        connection.exec_driver_sql(f"GRANT CREATE ON SCHEMA {quoted} TO PUBLIC")
    try:
        with Session(pg_engine) as db:
            with pytest.raises(PriceIntentUnavailable):
                _new_service(db, _keyring()).pin_trusted_schema()
    finally:
        with pg_engine.begin() as connection:
            connection.exec_driver_sql(f"REVOKE CREATE ON SCHEMA {quoted} FROM PUBLIC")


def test_only_expected_database_failures_are_classified():
    from app.services.doctor_price_intent_service import (
        PriceIntentConflict,
        PriceIntentRetryable,
        PriceIntentUnavailable,
        _raise_database_error,
    )

    class Original(Exception):
        def __init__(self, code):
            self.sqlstate = code

    def error(code):
        return sa.exc.DBAPIError("synthetic", {}, Original(code))

    for code, expected in (("23503", PriceIntentConflict), ("23505", PriceIntentConflict),
                           ("55P03", PriceIntentRetryable), ("42501", PriceIntentUnavailable)):
        with pytest.raises(expected):
            _raise_database_error(error(code), conflict=True)
    original = error("XX001")
    with pytest.raises(sa.exc.DBAPIError) as captured:
        _raise_database_error(original, conflict=True)
    assert captured.value is original


def test_operator_check_is_read_only_and_register_outputs_no_secrets(sqlite_engine):
    key = base64.urlsafe_b64encode(b"x" * 32).decode("ascii")
    env = os.environ.copy()
    env.update({"SECRET_KEY": "synthetic-jwt-secret-32-characters-long",
                "DOCTOR_PRICE_HMAC_KEYS": json.dumps({"1": key}),
                "DOCTOR_PRICE_HMAC_ACTIVE_VERSION": "1",
                "DATABASE_URL": str(sqlite_engine.url), "TESTING": "1"})
    cwd = str(Path(__file__).resolve().parents[2])

    def run(option):
        result = subprocess.run([sys.executable, "-m", "app.services.doctor_price_intent_service", option],
                                cwd=cwd, env=env, capture_output=True, text=True, timeout=30)
        assert key not in result.stdout + result.stderr
        assert env["DATABASE_URL"] not in result.stdout + result.stderr
        return result

    assert run("--check-keyring").returncode != 0
    with sqlite_engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_hmac_key_versions")).scalar_one() == 0
    assert run("--register-active").returncode == 0
    assert run("--check-keyring").returncode == 0
    with sqlite_engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_hmac_key_versions")).scalar_one() == 1






@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_explicit_modes_distinguish_retry_from_new_and_unknown_mode_conflicts(kind, request):
    from app.services.doctor_price_intent_service import (
        PriceIntentAmbiguous,
        PriceIntentConflict,
        PriceIntentInvalid,
    )
    engine = _engine(kind, request)
    with Session(engine) as db:
        service = _service(db, _keyring())
        _insert_intent(db, service, _payload())
        db.commit()
    with Session(engine) as db:
        service = _service(db, _keyring())
        with pytest.raises(PriceIntentAmbiguous):
            service.lookup(1, "schedule_next", _payload(), None)
        with pytest.raises(PriceIntentAmbiguous):
            service.lookup(1, "schedule_next", _payload(), "unknown")
        retry = service.lookup(1, "schedule_next", _payload(), "recover", mode="retry")
        assert retry.intent_id == 1 and retry.needs_alias
        # Actual endpoint must reauthorize and revalidate before binding.
        service.bind_alias(1, "schedule_next", 1, "recover")
        assert service.lookup(1, "schedule_next", _payload(), "recover", mode="new").intent_id == 1
        assert service.lookup(1, "schedule_next", _payload(), "brand-new", mode="new").intent_id is None
        with pytest.raises(PriceIntentConflict):
            service.lookup(1, "schedule_next", _payload(0), "recover", mode="new")
        with pytest.raises(PriceIntentConflict):
            service.lookup(1, "schedule_next", _payload(0), "missing", mode="retry")
        with pytest.raises(PriceIntentInvalid):
            service.lookup(1, "schedule_next", _payload(), None, mode="new")
        db.commit()


def test_postgres_actor_scope_is_nonblocking_and_reports_pending(pg_engine):
    from app.services.doctor_price_intent_service import PriceIntentPending
    with Session(pg_engine) as first, Session(pg_engine) as second:
        a = _new_service(first, _keyring())
        b = _new_service(second, _keyring())
        a.pin_trusted_schema()
        b.pin_trusted_schema()
        a.lock_actor_scope(1, "schedule_next")
        with pytest.raises(PriceIntentPending) as error:
            b.lock_actor_scope(1, "schedule_next")
        assert error.value.code == "pending_outcome"
        first.rollback()
        second.rollback()

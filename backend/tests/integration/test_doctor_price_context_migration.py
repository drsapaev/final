"""Synthetic 0112 migration tests with actual 0102/0103 triggers.

The predecessor omits unrelated tables; this is not a full-chain migration or
an endpoint, authorization, financial requote, or provider integration test.
"""
from __future__ import annotations

import importlib.util
import os
import threading
from concurrent.futures import ThreadPoolExecutor
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

_ROOT = Path(__file__).resolve().parents[2]


def _module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _migrate(connection, direction):
    migration = _module("price_context_0112", _ROOT / "alembic/versions/0112_doctor_price_context.py")
    migration.op = Operations(MigrationContext.configure(connection))
    getattr(migration, direction)()


def _predecessor(connection):
    old = _module("synthetic_evidence_predecessor", Path(__file__).with_name("test_visit_completion_evidence_pg.py"))
    old._setup_0102(connection)
    repeat = old._migration("0103_visit_consultation_completion.py")
    repeat.op = Operations(MigrationContext.configure(connection))
    repeat.upgrade()
    connection.execute(sa.text("ALTER TABLE doctors ADD COLUMN active BOOLEAN NOT NULL DEFAULT true"))
    connection.execute(sa.text("ALTER TABLE doctors ADD COLUMN specialty VARCHAR(100) NOT NULL DEFAULT 'cardiology'"))
    connection.execute(sa.text("ALTER TABLE doctors ADD COLUMN department_id INTEGER"))
    connection.execute(sa.text("ALTER TABLE visits ADD COLUMN encounter_id INTEGER"))
    connection.execute(sa.text("ALTER TABLE users ADD COLUMN auth_epoch BIGINT NOT NULL DEFAULT 0"))
    connection.execute(sa.text("""
        CREATE TABLE doctor_price_overrides (
          id INTEGER PRIMARY KEY, visit_id INTEGER REFERENCES visits(id) ON DELETE SET NULL,
          doctor_id INTEGER REFERENCES doctors(id) ON DELETE SET NULL,
          target_visit_service_id INTEGER REFERENCES visit_services(id) ON DELETE SET NULL
        )
    """))
    connection.execute(sa.text("""
        INSERT INTO visit_services (id,visit_id,service_id,name,qty,price,currency)
        VALUES (1,1,9,'synthetic',1,100,'UZS'),(2,1,10,'synthetic B',1,200,'UZS')
    """))
    connection.execute(sa.text("INSERT INTO doctor_price_overrides (id,visit_id,doctor_id,target_visit_service_id) VALUES (1,1,10,1)"))
    connection.execute(sa.text("""
        UPDATE visits SET confirmation_token='synthetic-token',
          repeat_proof_generation=repeat_evidence_generation,
          repeat_proof_consultation=true, repeat_proof_doctor_user_id=1 WHERE id=1
    """))


@pytest.fixture
def sqlite_engine(tmp_path, request):
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'context.sqlite'}")

    @sa.event.listens_for(engine, "connect")
    def configure(dbapi_connection, _):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")
        kind = getattr(getattr(request.node, "callspec", None), "params", {}).get("kind", "sqlite0")
        dbapi_connection.execute(f"PRAGMA recursive_triggers={int(kind == 'sqlite1')}")

    try:
        with engine.begin() as connection:
            _predecessor(connection)
            _migrate(connection, "upgrade")
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("DOCTOR_PRICE_TEST_DATABASE_URL") or os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable PostgreSQL clinic_test database")
    schema = "test_doctor_price_" + uuid4().hex
    admin = sa.create_engine(url)
    with admin.begin() as connection:
        connection.execute(CreateSchema(schema))
    engine = sa.create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        with engine.begin() as connection:
            _predecessor(connection)
            _migrate(connection, "upgrade")
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
            connection.execute(DropSchema(capability_schema_name(schema), cascade=True, if_exists=True))
        admin.dispose()


def _engine(kind, request):
    return request.getfixturevalue("sqlite_engine" if kind.startswith("sqlite") else "pg_engine")


def _value(connection, table, column, row_id):
    return connection.execute(sa.text(f"SELECT {column} FROM {table} WHERE id=:id"), {"id": row_id}).scalar_one()


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_legacy_snapshot_unknown_and_upgrade_preserves_existing_proofs(kind, request):
    with _engine(kind, request).connect() as connection:
        row = connection.execute(sa.text("SELECT * FROM doctor_price_overrides WHERE id=1")).mappings().one()
        assert all(row[col] is None for col in (
            "price_context_generation", "price_line_generation", "price_owner_generation", "doctor_user_auth_epoch",
            "requester_type", "requester_user_id", "requester_user_id_snapshot", "requester_auth_epoch",
        ))
        visit = connection.execute(sa.text("SELECT * FROM visits WHERE id=1")).mappings().one()
        assert visit["confirmation_token"] == "synthetic-token"
        assert visit["repeat_proof_generation"] == visit["repeat_evidence_generation"]
        assert visit["repeat_proof_doctor_user_id"] == 1
        assert visit["price_context_generation"] == 1
        assert _value(connection, "visit_services", "price_line_generation", 1) == 1
        assert _value(connection, "doctors", "price_owner_generation", 10) == 1


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
@pytest.mark.parametrize("table,row_id,generation,column,replacement", [
    ("visits", 1, "price_context_generation", "patient_id", 2),
    ("visits", 1, "price_context_generation", "doctor_id", 11),
    ("visits", 1, "price_context_generation", "visit_date", "2031-04-02"),
    ("visits", 1, "price_context_generation", "visit_time", "11:00"),
    ("visits", 1, "price_context_generation", "department", "other"),
    ("visits", 1, "price_context_generation", "department_id", 8),
    ("visits", 1, "price_context_generation", "encounter_id", 5),
    ("visits", 1, "price_context_generation", "discount_mode", "repeat"),
    ("visit_services", 1, "price_line_generation", "visit_id", 2),
    ("visit_services", 1, "price_line_generation", "service_id", 42),
    ("visit_services", 1, "price_line_generation", "code", "NEW"),
    ("visit_services", 1, "price_line_generation", "name", "new synthetic"),
    ("visit_services", 1, "price_line_generation", "duration_minutes_snapshot", 30),
    ("visit_services", 1, "price_line_generation", "qty", 2),
    ("visit_services", 1, "price_line_generation", "price", 101),
    ("visit_services", 1, "price_line_generation", "currency", "KZT"),
    ("doctors", 10, "price_owner_generation", "user_id", 2),
    ("doctors", 10, "price_owner_generation", "active", False),
    ("doctors", 10, "price_owner_generation", "specialty", "other"),
    ("doctors", 10, "price_owner_generation", "department_id", 9),
])
def test_material_change_and_aba_advance_generation(kind, table, row_id, generation, column, replacement, request):
    with _engine(kind, request).begin() as connection:
        previous_value = _value(connection, table, column, row_id)
        first = _value(connection, table, generation, row_id)
        connection.execute(sa.text(f"UPDATE {table} SET {column}={column} WHERE id=:id"), {"id": row_id})
        assert _value(connection, table, generation, row_id) == first
        connection.execute(sa.text(f"UPDATE {table} SET {column}=:value WHERE id=:id"), {"value": replacement, "id": row_id})
        second = _value(connection, table, generation, row_id)
        connection.execute(sa.text(f"UPDATE {table} SET {column}=:value WHERE id=:id"), {"value": previous_value, "id": row_id})
        third = _value(connection, table, generation, row_id)
        assert third > second > first


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_sibling_and_normal_confirmation_do_not_invalidate_price_context(kind, request):
    with _engine(kind, request).begin() as connection:
        visit = _value(connection, "visits", "price_context_generation", 1)
        line = _value(connection, "visit_services", "price_line_generation", 1)
        connection.execute(sa.text("UPDATE visit_services SET price=201 WHERE id=2"))
        assert _value(connection, "visits", "price_context_generation", 1) == visit
        assert _value(connection, "visit_services", "price_line_generation", 1) == line
        connection.execute(sa.text("UPDATE visits SET status='pending_confirmation' WHERE id=1"))
        connection.execute(sa.text("UPDATE visits SET status='confirmation_processing' WHERE id=1"))
        connection.execute(sa.text("UPDATE visits SET status='confirmed' WHERE id=1"))
        assert _value(connection, "visits", "price_context_generation", 1) == visit
        assert _value(connection, "visit_services", "price_line_generation", 1) == line


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_cancel_and_reopen_cannot_resurrect_visit_context(kind, request):
    with _engine(kind, request).begin() as connection:
        first = _value(connection, "visits", "price_context_generation", 1)
        connection.execute(sa.text("UPDATE visits SET status='canceled' WHERE id=1"))
        canceled = _value(connection, "visits", "price_context_generation", 1)
        connection.execute(sa.text("UPDATE visits SET status='confirmed' WHERE id=1"))
        reopened = _value(connection, "visits", "price_context_generation", 1)
        assert reopened > canceled > first


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
@pytest.mark.parametrize("table,row_id,generation", [
    ("visits", 1, "price_context_generation"),
    ("visit_services", 1, "price_line_generation"),
    ("doctors", 10, "price_owner_generation"),
])
def test_generation_cannot_be_rolled_back_and_primary_keys_cannot_be_changed(kind, table, row_id, generation, request):
    with _engine(kind, request).begin() as connection:
        column = {"visits": "visit_time", "visit_services": "name", "doctors": "specialty"}[table]
        connection.execute(sa.text(f"UPDATE {table} SET {column}='changed' WHERE id=:id"), {"id": row_id})
        current = _value(connection, table, generation, row_id)
        nested = connection.begin_nested()
        try:
            connection.execute(sa.text(f"UPDATE {table} SET {generation}=1 WHERE id=:id"), {"id": row_id})
        except DBAPIError:
            nested.rollback()
        else:
            nested.commit()
        assert _value(connection, table, generation, row_id) == current
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text(f"UPDATE {table} SET id=id+1000 WHERE id=:id"), {"id": row_id})


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_deleted_line_cannot_rebind_legacy_fk_and_reinsert_has_new_generation(kind, request):
    with _engine(kind, request).begin() as connection:
        old = _value(connection, "visit_services", "price_line_generation", 1)
        connection.execute(sa.text("DELETE FROM visit_services WHERE id=1"))
        assert _value(connection, "doctor_price_overrides", "target_visit_service_id", 1) is None
        connection.execute(sa.text("INSERT INTO visit_services (id,visit_id,service_id,name,qty,price) VALUES (1,1,9,'synthetic',1,100)"))
        assert _value(connection, "visit_services", "price_line_generation", 1) > old
        assert _value(connection, "doctor_price_overrides", "target_visit_service_id", 1) is None


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
@pytest.mark.parametrize("table,row_id", [("visits", 2), ("visit_services", 2), ("doctors", 11)])
def test_unreferenced_primary_key_cannot_be_changed(kind, table, row_id, request):
    with _engine(kind, request).begin() as connection:
        # Each row lacks references; failure is due to 0112 trigger, not an FK.
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text(f"UPDATE {table} SET id=id+1000 WHERE id=:id"), {"id": row_id})


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_generation_update_rolls_back_atomically(kind, request):
    with _engine(kind, request).begin() as connection:
        old = _value(connection, "visit_services", "price_line_generation", 1)
        savepoint = connection.begin_nested()
        connection.execute(sa.text("UPDATE visit_services SET price=101 WHERE id=1"))
        assert _value(connection, "visit_services", "price_line_generation", 1) > old
        savepoint.rollback()
        assert _value(connection, "visit_services", "price_line_generation", 1) == old
        assert _value(connection, "visit_services", "price", 1) == 100


def _intent(connection, ident=1, *, actor=1, operation="schedule_next", key=None,
            requester_type=None, doctor_id=10, owner=1):
    _register_version(connection, 1, "a" * 64)
    requester_type = requester_type or ("doctor" if actor == 1 else "admin")
    owner_epoch = 0 if owner is not None else None
    owner_generation = 1 if doctor_id is not None else None
    connection.execute(sa.text("""
        INSERT INTO doctor_price_intents
          (id,operation,requester_type,actor_user_id,actor_user_id_snapshot,actor_user_auth_epoch,
           doctor_id,doctor_id_snapshot,doctor_owner_user_id,doctor_owner_user_id_snapshot,
           patient_id,patient_id_snapshot,visit_id,visit_id_snapshot,
           doctor_user_auth_epoch,price_owner_generation,fingerprint_version,fingerprint)
        VALUES (:id,:operation,:requester_type,:actor,:actor,0,:doctor_id,:doctor_id,:owner,:owner,
                1,1,1,1,:owner_epoch,:owner_generation,1,:fingerprint)
    """), {"id": ident, "actor": actor, "operation": operation,
            "requester_type": requester_type, "doctor_id": doctor_id, "owner": owner,
            "owner_epoch": owner_epoch, "owner_generation": owner_generation,
            "fingerprint": "a" * 64})
    if key is not None:
        _attach_key(connection, ident=ident, intent=ident, actor=actor, operation=operation, key=key)


def _register_version(connection, version, digest):
    existing = connection.execute(sa.text("""
        SELECT key_check_digest FROM doctor_price_hmac_key_versions WHERE version=:version
    """), {"version": version}).scalar_one_or_none()
    if existing is None:
        connection.execute(sa.text("""
            INSERT INTO doctor_price_hmac_key_versions (version,key_check_digest) VALUES (:version,:digest)
        """), {"version": version, "digest": digest})
    else:
        assert existing == digest


def _attach_key(connection, *, ident, intent, actor=1, operation="schedule_next", key):
    connection.execute(sa.text("""
        INSERT INTO doctor_price_intent_keys (id,intent_id,actor_user_id_snapshot,operation,key_hash)
        VALUES (:id,:intent,:actor,:operation,:key)
    """), {"id": ident, "intent": intent, "actor": actor, "operation": operation, "key": key})


def _intent_line(connection, ident=1, intent=1, *, ordinal=0, raw=None, baseline=10000, proposed=10000):
    connection.execute(sa.text("""
        INSERT INTO doctor_price_intent_lines
          (id,intent_id,ordinal,service_id_snapshot,qty,raw_custom_minor,baseline_minor,
           proposed_minor,visit_service_id,visit_service_id_snapshot,override_id,override_id_snapshot)
        VALUES (:id,:intent,:ordinal,9,1,:raw,:baseline,:proposed,1,1,1,1)
    """), {"id": ident, "intent": intent, "ordinal": ordinal, "raw": raw,
            "baseline": baseline, "proposed": proposed})


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_admin_and_doctor_intent_owner_shapes(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection)
        _intent(connection, ident=2, actor=2, doctor_id=10, owner=1)
        _intent(connection, ident=3, actor=2, doctor_id=11, owner=None)
        _intent(connection, ident=4, actor=2, doctor_id=None, owner=None)
        row = connection.execute(sa.text("""
            SELECT requester_type,doctor_id_snapshot,price_owner_generation,
                   doctor_owner_user_id_snapshot,doctor_user_auth_epoch
            FROM doctor_price_intents WHERE id=4
        """)).one()
        assert tuple(row) == ("admin", None, None, None, None)
        for sql in (
            "UPDATE doctor_price_intents SET requester_type='doctor' WHERE id=4",
            "UPDATE doctor_price_intents SET requester_type='doctor' WHERE id=2",
            "UPDATE doctor_price_intents SET doctor_id_snapshot=NULL WHERE id=2",
            "UPDATE doctor_price_intents SET price_owner_generation=NULL WHERE id=2",
            "UPDATE doctor_price_intents SET doctor_owner_user_id_snapshot=NULL WHERE id=2",
            "UPDATE doctor_price_intents SET doctor_user_auth_epoch=NULL WHERE id=2",
            "UPDATE doctor_price_intents SET actor_user_auth_epoch=-1 WHERE id=2",
            "UPDATE doctor_price_intents SET requester_type='registrar' WHERE id=2",
        ):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(sql))


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_confirmation_snapshot_is_all_or_nothing_and_only_schedule(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection)
        _intent(connection, ident=2, operation="add_service")
        connection.execute(sa.text("""
            UPDATE doctor_price_intents SET issued_confirmation_epoch=9,
              issued_confirmation_digest=:digest,issued_confirmation_digest_version=1,
              issued_confirmation_expires_at='2031-04-03 12:00:00' WHERE id=1
        """), {"digest": "d" * 64})
        for sql in (
            "UPDATE doctor_price_intents SET issued_confirmation_epoch=NULL WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_digest=NULL WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_digest_version=NULL WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_expires_at=NULL WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_epoch=0 WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_digest_version=0 WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_digest='invalid' WHERE id=1",
            "UPDATE doctor_price_intents SET operation='add_service' WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_epoch=9 WHERE id=2",
        ):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(sql))
        columns = {col["name"] for col in sa.inspect(connection).get_columns("doctor_price_intents")}
        assert "confirmation_token" not in columns and "issued_confirmation_token" not in columns


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_registry_is_immutable_and_links_fingerprint_and_confirmation_versions(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection)
        _register_version(connection, 2, "b" * 64)
        columns = {col["name"] for col in sa.inspect(connection).get_columns("doctor_price_hmac_key_versions")}
        assert columns == {"version", "key_check_digest", "created_at"}
        connection.execute(sa.text("""
            UPDATE doctor_price_intents SET issued_confirmation_epoch=9,
              issued_confirmation_digest=:digest, issued_confirmation_digest_version=2,
              issued_confirmation_expires_at='2031-04-03 12:00:00' WHERE id=1
        """), {"digest": "d" * 64})
        for sql in (
            "UPDATE doctor_price_intents SET fingerprint_version=99 WHERE id=1",
            "UPDATE doctor_price_intents SET issued_confirmation_digest_version=99 WHERE id=1",
            "UPDATE doctor_price_hmac_key_versions SET key_check_digest=key_check_digest WHERE version=1",
            "UPDATE doctor_price_hmac_key_versions SET key_check_digest='replacement' WHERE version=2",
            "DELETE FROM doctor_price_hmac_key_versions WHERE version=1",
            "DELETE FROM doctor_price_hmac_key_versions WHERE version=2",
            "INSERT INTO doctor_price_hmac_key_versions (version,key_check_digest) VALUES (0, 'bad')",
            "INSERT INTO doctor_price_hmac_key_versions (version,key_check_digest) VALUES (3, 'bad')",
            f"INSERT INTO doctor_price_hmac_key_versions (version,key_check_digest) VALUES (4, '{'z' * 64}')",
        ):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(sql))
        connection.execute(sa.text("UPDATE doctor_price_intents SET fingerprint_version=2 WHERE id=1"))
        rows = connection.execute(sa.text("SELECT version,key_check_digest FROM doctor_price_hmac_key_versions ORDER BY version")).all()
        assert rows == [(1, "a" * 64), (2, "b" * 64)]


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_registry_concurrent_version_conflict_detects_mismatched_commitment(kind, request):
    engine = _engine(kind, request)
    barrier = threading.Barrier(2)
    committed = threading.Event()

    def worker(digest):
        try:
            with engine.begin() as connection:
                barrier.wait(timeout=10)
                connection.execute(sa.text("""
                    INSERT INTO doctor_price_hmac_key_versions (version,key_check_digest) VALUES (2,:digest)
                """), {"digest": digest})
            committed.set()
        except DBAPIError:
            assert committed.wait(timeout=10)
        with engine.connect() as connection:
            observed = connection.execute(sa.text("""
                SELECT key_check_digest FROM doctor_price_hmac_key_versions WHERE version=2
            """)).scalar_one()
        return observed == digest

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, ("b" * 64, "c" * 64)))
    assert sorted(results) == [False, True]


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_downgrade_fails_with_registry_commitment_only(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _register_version(connection, 1, "a" * 64)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _migrate(connection, "downgrade")
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT key_check_digest FROM doctor_price_hmac_key_versions WHERE version=1")).scalar_one() == "a" * 64


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_requester_override_group_constraints_and_deleted_actor_history(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection, key="b" * 64)
        connection.execute(sa.text("""
            UPDATE doctor_price_overrides SET requester_type='doctor',requester_user_id=1,
              requester_user_id_snapshot=1,requester_auth_epoch=0 WHERE id=1
        """))
        for sql in (
            "UPDATE doctor_price_overrides SET requester_type=NULL WHERE id=1",
            "UPDATE doctor_price_overrides SET requester_user_id_snapshot=NULL WHERE id=1",
            "UPDATE doctor_price_overrides SET requester_auth_epoch=NULL WHERE id=1",
            "UPDATE doctor_price_overrides SET requester_user_id=2 WHERE id=1",
            "UPDATE doctor_price_overrides SET requester_type='registrar' WHERE id=1",
        ):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(sql))
        connection.execute(sa.text("DELETE FROM users WHERE id=1"))
        override = connection.execute(sa.text("""
            SELECT requester_user_id,requester_user_id_snapshot,requester_auth_epoch
            FROM doctor_price_overrides WHERE id=1
        """)).one()
        assert tuple(override) == (None, 1, 0)
        intent = connection.execute(sa.text("""
            SELECT actor_user_id,actor_user_id_snapshot,doctor_owner_user_id,
                   doctor_owner_user_id_snapshot,doctor_user_auth_epoch
            FROM doctor_price_intents WHERE id=1
        """)).one()
        assert tuple(intent) == (None, 1, None, 1, 0)
        assert connection.execute(sa.text("""
            SELECT actor_user_id_snapshot,key_hash FROM doctor_price_intent_keys WHERE intent_id=1
        """)).one() == (1, "b" * 64)


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_intent_prices_preserve_absent_zero_and_exact_maximum(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection)
        for ident, raw in enumerate((None, 0, 999999999999), start=1):
            _intent_line(connection, ident=ident, ordinal=ident, raw=raw, proposed=raw or 0)
        rows = connection.execute(sa.text("SELECT raw_custom_minor FROM doctor_price_intent_lines ORDER BY id")).scalars().all()
        assert rows == [None, 0, 999999999999]
        for column, value in (("raw_custom_minor", -1), ("raw_custom_minor", 1000000000000),
                              ("baseline_minor", -1), ("baseline_minor", 1000000000000),
                              ("proposed_minor", -1), ("proposed_minor", 1000000000000),
                              ("qty", 0), ("ordinal", -1)):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(f"UPDATE doctor_price_intent_lines SET {column}=:v WHERE id=1"), {"v": value})


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_intent_key_scoped_by_actor_operation_and_line_ordinal(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection, key="b" * 64)
        _intent(connection, ident=2, actor=2, key="b" * 64)
        _intent(connection, ident=3, operation="add_service", key="b" * 64)
        _intent(connection, ident=4, key=None)
        _intent(connection, ident=5, key=None)
        with pytest.raises(DBAPIError), connection.begin_nested():
            _intent(connection, ident=6, key="b" * 64)
        _intent_line(connection)
        with pytest.raises(DBAPIError), connection.begin_nested():
            _intent_line(connection, ident=2)
        _intent_line(connection, ident=3, ordinal=1)
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("DELETE FROM doctor_price_intents WHERE id=1"))


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_intent_aliases_are_bound_to_header_identity_and_restrict_deletion(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection)
        _intent(connection, ident=2)
        _attach_key(connection, ident=1, intent=1, key="a" * 64)
        _attach_key(connection, ident=2, intent=1, key="b" * 64)
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intent_keys WHERE intent_id=1")).scalar_one() == 2
        for sql, key in (
            ("INSERT INTO doctor_price_intent_keys (id,intent_id,actor_user_id_snapshot,operation,key_hash) VALUES (3,2,1,'schedule_next',:key)", "a" * 64),
            ("INSERT INTO doctor_price_intent_keys (id,intent_id,actor_user_id_snapshot,operation,key_hash) VALUES (4,1,2,'schedule_next',:key)", "c" * 64),
            ("INSERT INTO doctor_price_intent_keys (id,intent_id,actor_user_id_snapshot,operation,key_hash) VALUES (5,1,1,'add_service',:key)", "d" * 64),
            ("INSERT INTO doctor_price_intent_keys (id,intent_id,actor_user_id_snapshot,operation,key_hash) VALUES (6,1,1,'schedule_next',:key)", "z" * 64),
        ):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(sql), {"key": key})
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("DELETE FROM doctor_price_intents WHERE id=1"))


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_intent_preserves_snapshots_after_deleting_live_line_and_override(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection)
        _intent_line(connection, raw=0)
        connection.execute(sa.text("DELETE FROM doctor_price_overrides WHERE id=1"))
        connection.execute(sa.text("DELETE FROM visit_services WHERE id=1"))
        row = connection.execute(sa.text("""
            SELECT visit_service_id,visit_service_id_snapshot,override_id,override_id_snapshot
            FROM doctor_price_intent_lines WHERE id=1
        """)).one()
        assert tuple(row) == (None, 1, None, 1)


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_intent_live_override_requires_snapshot(kind, request):
    with _engine(kind, request).begin() as connection:
        _intent(connection)
        _intent_line(connection)
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("UPDATE doctor_price_intent_lines SET override_id_snapshot=NULL WHERE id=1"))


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_concurrent_identical_client_key_has_one_winner(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _register_version(connection, 1, "a" * 64)
    barrier = threading.Barrier(2)

    def worker(ident):
        try:
            with engine.begin() as connection:
                barrier.wait(timeout=10)
                _intent(connection, ident=ident, key="f" * 64)
            return "committed"
        except DBAPIError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, (21, 22)))
    assert sorted(results) == ["committed", "conflict"]
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intent_keys WHERE key_hash=:key"), {"key": "f" * 64}).scalar_one() == 1


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_concurrent_distinct_keys_attach_to_same_existing_no_key_intent(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _intent(connection)
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intent_keys")).scalar_one() == 0
    barrier = threading.Barrier(2)

    def worker(pair):
        ident, key = pair
        with engine.begin() as connection:
            barrier.wait(timeout=10)
            _attach_key(connection, ident=ident, intent=1, key=key)

    with ThreadPoolExecutor(max_workers=2) as executor:
        list(executor.map(worker, ((31, "c" * 64), (32, "d" * 64))))
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intent_keys WHERE intent_id=1")).scalar_one() == 2


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_concurrent_line_changes_get_distinct_committed_generations(kind, request):
    engine = _engine(kind, request)
    barrier = threading.Barrier(2)

    def worker(price):
        with engine.begin() as connection:
            barrier.wait(timeout=10)
            connection.execute(sa.text("UPDATE visit_services SET price=:price WHERE id=1"), {"price": price})
            return _value(connection, "visit_services", "price_line_generation", 1)

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(worker, (101, 102)))
    assert len(set(results)) == 2
    with engine.connect() as connection:
        assert _value(connection, "visit_services", "price_line_generation", 1) == max(results)


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_downgrade_fails_closed_with_durable_intent(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _intent(connection)
        _intent_line(connection)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _migrate(connection, "downgrade")
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intents")).scalar_one() == 1
        assert _value(connection, "visit_services", "price_line_generation", 1) == 1


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_downgrade_keeps_all_key_aliases(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        _intent(connection, key="a" * 64)
        _attach_key(connection, ident=2, intent=1, key="b" * 64)
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _migrate(connection, "downgrade")
    with engine.connect() as connection:
        assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intent_keys WHERE intent_id=1")).scalar_one() == 2


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_downgrade_fails_closed_with_binding_snapshot(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        connection.execute(sa.text("UPDATE doctor_price_overrides SET price_line_generation=1 WHERE id=1"))
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _migrate(connection, "downgrade")


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1", "postgresql"])
def test_downgrade_fails_closed_with_only_requester_snapshot(kind, request):
    engine = _engine(kind, request)
    with engine.begin() as connection:
        connection.execute(sa.text("""
            UPDATE doctor_price_overrides SET requester_type='admin',requester_user_id=1,
              requester_user_id_snapshot=1,requester_auth_epoch=0 WHERE id=1
        """))
    with pytest.raises(DBAPIError), engine.begin() as connection:
        _migrate(connection, "downgrade")


def test_postgres_new_tables_have_default_deny_rls(pg_engine):
    with pg_engine.connect() as connection:
        for name in ("doctor_price_intents", "doctor_price_intent_lines", "doctor_price_intent_keys", "doctor_price_hmac_key_versions"):
            row = connection.execute(sa.text("""
                SELECT c.relrowsecurity,
                       (SELECT count(*) FROM pg_policy p WHERE p.polrelid=c.oid)
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=current_schema() AND c.relname=:name
            """), {"name": name}).one()
            assert tuple(row) == (True, 0)


def test_postgres_nonowner_can_advance_generation_without_sequence_access(pg_engine):
    role = "test_price_runtime_" + uuid4().hex
    role_q = pg_engine.dialect.identifier_preparer.quote(role)
    with pg_engine.begin() as connection:
        can_create = connection.execute(sa.text("SELECT rolsuper OR rolcreaterole FROM pg_roles WHERE rolname=current_user")).scalar_one()
        if not can_create:
            pytest.skip("requires disposable PostgreSQL role creation privileges")
        schema = connection.execute(sa.text("SELECT current_schema()")).scalar_one()
        schema_q = connection.dialect.identifier_preparer.quote(schema)
        connection.exec_driver_sql(f"CREATE ROLE {role_q} NOLOGIN NOBYPASSRLS")
        connection.exec_driver_sql(f"GRANT USAGE ON SCHEMA {schema_q} TO {role_q}")
        connection.exec_driver_sql(f"GRANT SELECT, UPDATE ON {schema_q}.visits TO {role_q}")
        connection.exec_driver_sql(f"GRANT SELECT ON {schema_q}.doctor_price_intents TO {role_q}")
        connection.exec_driver_sql(f"GRANT SELECT ON {schema_q}.doctor_price_intent_keys TO {role_q}")
        connection.exec_driver_sql(f"GRANT SELECT ON {schema_q}.doctor_price_hmac_key_versions TO {role_q}")
        _intent(connection, key="b" * 64)
    try:
        with pg_engine.begin() as connection:
            connection.exec_driver_sql(f"SET LOCAL ROLE {role_q}")
            assert connection.execute(sa.text("""
                SELECT has_sequence_privilege(current_user, c.oid, 'USAGE')
                FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
                WHERE n.nspname=current_schema() AND c.relname='doctor_price_generation_seq'
            """)).scalar_one() is False
            assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intents")).scalar_one() == 0
            assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_intent_keys")).scalar_one() == 0
            assert connection.execute(sa.text("SELECT COUNT(*) FROM doctor_price_hmac_key_versions")).scalar_one() == 0
            before = _value(connection, "visits", "price_context_generation", 1)
            connection.execute(sa.text("UPDATE visits SET visit_time='12:00' WHERE id=1"))
            assert _value(connection, "visits", "price_context_generation", 1) > before
    finally:
        with pg_engine.begin() as connection:
            connection.exec_driver_sql(f"DROP OWNED BY {role_q}")
            connection.exec_driver_sql(f"DROP ROLE {role_q}")


def test_postgres_owner_cannot_truncate_registry_even_with_cascade(pg_engine):
    with pg_engine.begin() as connection:
        _register_version(connection, 1, "a" * 64)
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("TRUNCATE doctor_price_hmac_key_versions CASCADE"))
        assert connection.execute(sa.text("SELECT key_check_digest FROM doctor_price_hmac_key_versions WHERE version=1")).scalar_one() == "a" * 64


def test_sqlite_clock_cannot_be_reset_replaced_or_deleted(sqlite_engine):
    with sqlite_engine.begin() as connection:
        connection.execute(sa.text("UPDATE visit_services SET price=101 WHERE id=1"))
        for sql in ("UPDATE doctor_price_generation_clock SET value=0",
                    "DELETE FROM doctor_price_generation_clock",
                    "INSERT OR REPLACE INTO doctor_price_generation_clock (id,value) VALUES (1,0)"):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(sql))


@pytest.mark.parametrize("kind", ["sqlite0", "sqlite1"])
def test_sqlite_registry_rejects_replace_even_when_recursive_triggers_disabled(kind, request):
    with _engine(kind, request).begin() as connection:
        _register_version(connection, 1, "a" * 64)
        for verb in ("INSERT OR REPLACE", "INSERT OR IGNORE"):
            with pytest.raises(DBAPIError), connection.begin_nested():
                connection.execute(sa.text(f"""
                    {verb} INTO doctor_price_hmac_key_versions(version,key_check_digest) VALUES (1,:digest)
                """), {"digest": "b" * 64})
        assert connection.execute(sa.text("SELECT key_check_digest FROM doctor_price_hmac_key_versions WHERE version=1")).scalar_one() == "a" * 64


@pytest.mark.parametrize("column", ["raw_custom_minor", "baseline_minor", "proposed_minor", "qty", "service_id_snapshot"])
def test_sqlite_rejects_real_storage_for_integer_money_and_identity(sqlite_engine, column):
    with sqlite_engine.begin() as connection:
        _intent(connection)
        _intent_line(connection)
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text(f"UPDATE doctor_price_intent_lines SET {column}=1.5 WHERE id=1"))


@pytest.mark.parametrize("column", ["actor_user_auth_epoch", "doctor_user_auth_epoch", "price_owner_generation"])
def test_sqlite_rejects_real_requester_and_owner_epochs(sqlite_engine, column):
    with sqlite_engine.begin() as connection:
        _intent(connection)
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text(f"UPDATE doctor_price_intents SET {column}=1.5 WHERE id=1"))


@pytest.mark.parametrize("column", ["issued_confirmation_epoch", "issued_confirmation_digest_version"])
def test_sqlite_rejects_real_confirmation_epoch_and_version(sqlite_engine, column):
    with sqlite_engine.begin() as connection:
        _intent(connection)
        connection.execute(sa.text("""
            UPDATE doctor_price_intents SET issued_confirmation_epoch=9, issued_confirmation_digest=:digest,
              issued_confirmation_digest_version=1, issued_confirmation_expires_at='2031-04-03 12:00:00'
            WHERE id=1
        """), {"digest": "d" * 64})
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text(f"UPDATE doctor_price_intents SET {column}=1.5 WHERE id=1"))


@pytest.mark.parametrize("column", ["requester_user_id_snapshot", "requester_auth_epoch"])
def test_sqlite_rejects_real_override_requester_snapshot(sqlite_engine, column):
    with sqlite_engine.begin() as connection:
        connection.execute(sa.text("""
            UPDATE doctor_price_overrides SET requester_type='admin',requester_user_id=NULL,
              requester_user_id_snapshot=1,requester_auth_epoch=0 WHERE id=1
        """))
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text(f"UPDATE doctor_price_overrides SET {column}=1.5 WHERE id=1"))


def test_sqlite_after_insert_requires_refresh_before_binding(sqlite_engine):
    with sqlite_engine.begin() as connection:
        returned = connection.execute(sa.text("""
            INSERT INTO visit_services (id,visit_id,service_id,name,qty,price,price_line_generation)
            VALUES (3,1,12,'synthetic',1,10,777777) RETURNING price_line_generation
        """)).scalar_one()
        stored = _value(connection, "visit_services", "price_line_generation", 3)
        assert returned == 777777
        assert 1 < stored != returned


def test_sqlite_clock_overflow_aborts_the_business_update(sqlite_engine):
    with sqlite_engine.begin() as connection:
        # Synthetic fixture only: temporarily remove the guard to put the clock
        # at its terminal value, then restore the exact migration trigger.
        guards = connection.execute(sa.text("""
            SELECT name,sql FROM sqlite_master WHERE type='trigger'
              AND tbl_name='doctor_price_generation_clock' AND upper(sql) LIKE '%BEFORE UPDATE%'
        """)).all()
        assert guards
        for name, _ in guards:
            connection.exec_driver_sql(f'DROP TRIGGER "{name}"')
        connection.execute(sa.text("UPDATE doctor_price_generation_clock SET value=9223372036854775807"))
        for _, sql in guards:
            connection.exec_driver_sql(sql)
        old = _value(connection, "visit_services", "price_line_generation", 1)
        with pytest.raises(DBAPIError), connection.begin_nested():
            connection.execute(sa.text("UPDATE visit_services SET price=101 WHERE id=1"))
        assert _value(connection, "visit_services", "price", 1) == 100
        assert _value(connection, "visit_services", "price_line_generation", 1) == old


@pytest.mark.parametrize("kind", ["sqlite", "postgresql"])
def test_recent_actor_operation_scan_has_durable_index(kind, request):
    engine = _engine(kind, request)
    indexes = {index["name"]: index for index in sa.inspect(engine).get_indexes("doctor_price_intents")}
    assert indexes["ix_doctor_price_intent_recent"]["column_names"] == ["actor_user_id_snapshot", "operation", "created_at"]
    assert indexes["ix_doctor_price_intent_fingerprint"]["column_names"] == ["actor_user_id_snapshot", "operation", "fingerprint_version", "fingerprint"]


def test_postgres_trusted_schema_pins_ddl_and_sequence_against_shadow_and_quoting(pg_engine):
    """An attacker-writable earlier schema cannot redirect privileged DDL."""
    trusted = "t11_$doctor_price_guard$_$doctor_price_function$_$$'\"_" + uuid4().hex[:8]
    shadow = "t11_shadow_" + uuid4().hex[:8]
    quote = pg_engine.dialect.identifier_preparer.quote_identifier
    tq, sq = quote(trusted), quote(shadow)
    migration = _module("price_context_schema_shadow_0112", _ROOT / "alembic/versions/0112_doctor_price_context.py")
    try:
        with pg_engine.begin() as connection:
            connection.exec_driver_sql(f"CREATE SCHEMA {tq}")
            connection.exec_driver_sql(f"CREATE SCHEMA {sq}")
            connection.exec_driver_sql(f"GRANT CREATE ON SCHEMA {sq} TO PUBLIC")
            connection.exec_driver_sql(f"SET LOCAL search_path TO {tq}, pg_catalog")
            _predecessor(connection)
            connection.exec_driver_sql(f"CREATE TABLE {sq}.visits (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TEMP TABLE visits (id INTEGER PRIMARY KEY)")
            connection.exec_driver_sql("CREATE TEMP TABLE doctor_price_hmac_key_versions (version INTEGER)")
            connection.exec_driver_sql(f"CREATE SEQUENCE {sq}.doctor_price_generation_seq START WITH 77")
            connection.exec_driver_sql(f"SET LOCAL search_path TO {sq}, {tq}, pg_catalog")
            original_path = connection.execute(sa.text("SHOW search_path")).scalar_one()
            migration.op = Operations(MigrationContext.configure(connection, opts={"version_table_schema": trusted}))
            migration.upgrade()
            assert connection.execute(sa.text("SHOW search_path")).scalar_one() == original_path
            assert connection.execute(sa.text("""
                SELECT count(*) FROM pg_catalog.pg_attribute
                WHERE attrelid=pg_catalog.to_regclass('pg_temp.visits')
                  AND attname='price_context_generation' AND NOT attisdropped
            """)).scalar_one() == 0
            assert "price_context_generation" in {
                col["name"] for col in sa.inspect(connection).get_columns("visits", schema=trusted)
            }
            assert "price_context_generation" not in {
                col["name"] for col in sa.inspect(connection).get_columns("visits", schema=shadow)
            }
            connection.exec_driver_sql(f"UPDATE {tq}.visits SET visit_time='12:00' WHERE id=1")
            assert connection.exec_driver_sql(f"SELECT price_context_generation FROM {tq}.visits WHERE id=1").scalar_one() > 1
            assert connection.exec_driver_sql(f"SELECT is_called FROM {sq}.doctor_price_generation_seq").scalar_one() is False
    finally:
        with pg_engine.begin() as connection:
            connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {sq} CASCADE")
            connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {tq} CASCADE")
            connection.execute(DropSchema(capability_schema_name(trusted), cascade=True, if_exists=True))


@pytest.mark.parametrize("explicit_role", [False, True], ids=["public", "specific-nonowner"])
def test_postgres_rejects_nonowner_create_on_anchor_before_schema_changes(pg_engine, explicit_role):
    trusted = "t11_untrusted_" + uuid4().hex[:8]
    role = "t11_writer_" + uuid4().hex[:8]
    tq = pg_engine.dialect.identifier_preparer.quote_identifier(trusted)
    rq = pg_engine.dialect.identifier_preparer.quote_identifier(role)
    migration = _module("price_context_schema_guard_0112", _ROOT / "alembic/versions/0112_doctor_price_context.py")
    try:
        with pg_engine.begin() as connection:
            if explicit_role:
                connection.exec_driver_sql(f"CREATE ROLE {rq} NOLOGIN")
            connection.exec_driver_sql(f"CREATE SCHEMA {tq}")
            connection.exec_driver_sql(f"SET LOCAL search_path TO {tq}, pg_catalog")
            _predecessor(connection)
            connection.exec_driver_sql(f"GRANT CREATE ON SCHEMA {tq} TO {rq if explicit_role else 'PUBLIC'}")
        with pytest.raises(DBAPIError, match="schema is not trusted"), pg_engine.begin() as connection:
            migration.op = Operations(MigrationContext.configure(connection, opts={"version_table_schema": trusted}))
            migration.upgrade()
        assert "price_context_generation" not in {
            col["name"] for col in sa.inspect(pg_engine).get_columns("visits", schema=trusted)
        }
    finally:
        with pg_engine.begin() as connection:
            connection.exec_driver_sql(f"DROP SCHEMA IF EXISTS {tq} CASCADE")
            if explicit_role:
                connection.exec_driver_sql(f"DROP ROLE {rq}")


def test_offline_postgres_requires_explicit_schema():
    import io
    migration = _module("price_context_offline_0112", _ROOT / "alembic/versions/0112_doctor_price_context.py")
    context = MigrationContext.configure(url="postgresql://", opts={"as_sql": True, "output_buffer": io.StringIO()})
    migration.op = Operations(context)
    with pytest.raises(RuntimeError, match="explicit trusted schema"):
        migration.upgrade()

"""Real 0104 operations, RLS and patient-consistency on disposable databases."""

import importlib.util
import io
import os
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

_VERSIONS = Path(__file__).resolve().parents[2] / "alembic/versions"


def _migration(filename):
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), _VERSIONS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _setup_0103(conn):
    conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    conn.execute(text("INSERT INTO users (id) VALUES (1)"))
    conn.execute(text("CREATE TABLE doctors (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL)"))
    conn.execute(text("INSERT INTO doctors (id, user_id) VALUES (10, 1)"))
    conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, phone VARCHAR(64))"))
    conn.execute(text("INSERT INTO patients (id, phone) VALUES (1, 'synthetic'), (2, 'synthetic'), (3, 'synthetic')"))
    # Nullable/missing patient ids deliberately model damaged historic data;
    # normal current visits have an enforced non-null patient FK.
    conn.execute(text("""
        CREATE TABLE visits (
          id INTEGER PRIMARY KEY, patient_id INTEGER, doctor_id INTEGER REFERENCES doctors(id) ON DELETE SET NULL,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          visit_date DATE, visit_time VARCHAR(8), department VARCHAR(64), department_id INTEGER,
          discount_mode VARCHAR(32), confirmation_channel VARCHAR(16), status VARCHAR(32) NOT NULL,
          confirmation_token VARCHAR(128), confirmation_expires_at TIMESTAMP,
          reminder_sent_at TIMESTAMP, reminder_generation INTEGER NOT NULL DEFAULT 0,
          reminder_claimed_at TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE TABLE visit_services (
          id INTEGER PRIMARY KEY, visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE,
          service_id INTEGER, code VARCHAR(64), name VARCHAR(255), duration_minutes_snapshot INTEGER,
          qty INTEGER, price NUMERIC(12,2), currency VARCHAR(8)
        )
    """))
    conn.execute(text("""
        CREATE TABLE payment_invoice_visits (invoice_id INTEGER, visit_id INTEGER)
    """))
    conn.execute(text("""
        CREATE TABLE appointments (
          id INTEGER PRIMARY KEY,
          patient_id INTEGER NOT NULL REFERENCES patients(id) ON DELETE RESTRICT
        )
    """))
    conn.execute(text("""
        CREATE TABLE queue_entries (
          id INTEGER PRIMARY KEY,
          patient_id INTEGER REFERENCES patients(id) ON DELETE SET NULL,
          visit_id INTEGER REFERENCES visits(id) ON DELETE SET NULL
        )
    """))
    conn.execute(text("""
        INSERT INTO visits (id, patient_id, doctor_id, visit_date, status, confirmation_token)
        VALUES (1,1,10,'2031-04-01','completed','token-one'),
               (2,1,10,'2031-04-01','completed','token-two'),
               (3,2,10,'2031-04-01','completed','token-three'),
               (4,999,10,'2031-04-01','completed','token-four'),
               (5,NULL,10,'2031-04-01','completed','token-five')
    """))
    # A shared invoice does not prove that these visits were one encounter.
    conn.execute(text("INSERT INTO payment_invoice_visits (invoice_id, visit_id) VALUES (1,1), (1,2)"))
    conn.execute(text("INSERT INTO appointments (id, patient_id) VALUES (1,1), (2,2)"))
    # Row 2 is an intentionally mismatched historical queue reference. It
    # remains unresolved because migration must not guess its encounter.
    conn.execute(text("INSERT INTO queue_entries (id,patient_id,visit_id) VALUES (1,1,1), (2,2,1), (3,1,NULL), (4,3,NULL)"))
    for filename in ("0102_visit_confirmation_context.py", "0103_visit_consultation_completion.py"):
        migration = _migration(filename)
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
    conn.execute(text("""
        UPDATE visits SET repeat_proof_generation=repeat_evidence_generation,
          repeat_proof_consultation=true, repeat_proof_doctor_user_id=1 WHERE id=1
    """))


def _visit(conn, visit_id):
    return conn.execute(text("SELECT * FROM visits WHERE id=:id"), {"id": visit_id}).mappings().one()


def _assert_fails_in_savepoint(conn, operation):
    nested = conn.begin_nested()
    try:
        with pytest.raises(DBAPIError):
            operation()
    finally:
        nested.rollback()


def _flush_deferred(conn):
    if conn.dialect.name == "postgresql":
        conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))


def _assert_downgrade_blocked(conn, migration, mutate):
    nested = conn.begin_nested()
    try:
        mutate()
        before = conn.execute(text("SELECT count(*) FROM encounters")).scalar_one()
        with pytest.raises(DBAPIError):
            migration.downgrade()
        # PG marks the savepoint aborted after the intentional exception;
        # verify intact state after rollback below.
        assert before > 0
    finally:
        nested.rollback()
    assert conn.execute(text("SELECT count(*) FROM encounters")).scalar_one() == 5


def _exercise(conn):
    _setup_0103(conn)
    before = dict(_visit(conn, 1))
    migration = _migration("0104_encounters.py")
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    rows = conn.execute(text("SELECT * FROM encounters ORDER BY legacy_visit_id")).mappings().all()
    assert len(rows) == 5
    assert [row["legacy_visit_id"] for row in rows] == [1, 2, 3, 4, 5]
    assert all(row["provenance"] == "legacy_unresolved" and row["generation"] > 0 for row in rows)
    assert [row["patient_id"] for row in rows] == [1, 1, 2, None, None]
    assert len({_visit(conn, visit_id)["encounter_id"] for visit_id in (1, 2, 3)}) == 3
    assert _visit(conn, 4)["encounter_id"] is None
    assert _visit(conn, 5)["encounter_id"] is None
    assert conn.execute(text("SELECT count(*) FROM appointments WHERE encounter_id IS NOT NULL OR source_visit_id IS NOT NULL")).scalar_one() == 0
    assert conn.execute(text("SELECT count(*) FROM queue_entries WHERE encounter_id IS NOT NULL")).scalar_one() == 0
    assert conn.execute(text("SELECT patient_id FROM queue_entries WHERE id=2")).scalar_one() == 2
    # Backfill only attaches grouping; existing 0102/0103 capabilities and
    # proof are not reissued or accidentally invalidated.
    after = _visit(conn, 1)
    for field in ("confirmation_token", "confirmation_context_epoch", "repeat_evidence_generation",
                  "repeat_proof_generation", "repeat_proof_consultation", "repeat_proof_doctor_user_id"):
        assert after[field] == before[field]

    if conn.dialect.name == "postgresql":
        assert conn.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid='encounters'::regclass")).scalar_one()
        assert conn.execute(text("SELECT count(*) FROM pg_policies WHERE schemaname=current_schema() AND tablename='encounters' ")).scalar_one() == 0
        # This builtin role may read all tables but does NOT bypass RLS.
        conn.execute(text("SET LOCAL ROLE pg_read_all_data"))
        assert conn.execute(text("SELECT count(*) FROM encounters")).scalar_one() == 0
        conn.execute(text("RESET ROLE"))
        assert conn.execute(text("SELECT count(*) FROM encounters")).scalar_one() == 5

    e1, e2, e3 = (_visit(conn, visit_id)["encounter_id"] for visit_id in (1, 2, 3))

    def mismatch_visit():
        conn.execute(text("UPDATE visits SET encounter_id=:id WHERE id=1"), {"id": e3})
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, mismatch_visit)
    assert _visit(conn, 1)["encounter_id"] == e1

    def mismatch_encounter():
        conn.execute(text("UPDATE encounters SET patient_id=2 WHERE id=:id"), {"id": e1})
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, mismatch_encounter)

    def missing_encounter():
        conn.execute(text("UPDATE visits SET encounter_id=99999999 WHERE id=1"))
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, missing_encounter)

    def null_patient_on_link():
        conn.execute(text("UPDATE visits SET patient_id=NULL WHERE id=1"))
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, null_patient_on_link)

    def new_encounter_without_patient():
        conn.execute(text("INSERT INTO encounters (patient_id,provenance) VALUES (NULL,'new')"))
    _assert_fails_in_savepoint(conn, new_encounter_without_patient)

    def wrong_source_patient():
        conn.execute(text("UPDATE appointments SET source_visit_id=1 WHERE id=2"))
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, wrong_source_patient)

    def foreign_queue_patient():
        conn.execute(text("UPDATE queue_entries SET encounter_id=:id WHERE id=2"), {"id": e1})
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, foreign_queue_patient)

    def queue_without_patient():
        conn.execute(text("INSERT INTO queue_entries (id,patient_id,encounter_id) VALUES (10,NULL,:id)"), {"id": e1})
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, queue_without_patient)

    # New, explicitly sourced rows are bound to the same patient and group.
    child = conn.begin_nested()
    conn.execute(text("UPDATE appointments SET encounter_id=:id, source_visit_id=1 WHERE id=1"), {"id": e1})
    conn.execute(text("UPDATE queue_entries SET encounter_id=:id WHERE id=1"), {"id": e1})
    _flush_deferred(conn)

    def wrong_same_patient_group():
        conn.execute(text("UPDATE appointments SET source_visit_id=2 WHERE id=1"))
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, wrong_same_patient_group)

    def wrong_queue_group():
        conn.execute(text("UPDATE queue_entries SET encounter_id=:id WHERE id=1"), {"id": e2})
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, wrong_queue_group)

    def move_sourced_visit_without_children():
        conn.execute(text("UPDATE visits SET encounter_id=:id WHERE id=1"), {"id": e2})
        _flush_deferred(conn)
    _assert_fails_in_savepoint(conn, move_sourced_visit_without_children)

    anonymize_queue = conn.begin_nested()
    conn.execute(text("UPDATE queue_entries SET patient_id=NULL WHERE id=1"))
    queue = conn.execute(text("SELECT patient_id,visit_id,encounter_id FROM queue_entries WHERE id=1")).mappings().one()
    assert queue["patient_id"] is None and queue["encounter_id"] is None and queue["visit_id"] == 1
    anonymize_queue.rollback()

    remove_source = conn.begin_nested()
    conn.execute(text("DELETE FROM visits WHERE id=1"))
    appointment = conn.execute(text("SELECT patient_id,source_visit_id,encounter_id FROM appointments WHERE id=1")).mappings().one()
    queue = conn.execute(text("SELECT patient_id,visit_id,encounter_id FROM queue_entries WHERE id=1")).mappings().one()
    assert appointment["patient_id"] == 1 and appointment["source_visit_id"] is None and appointment["encounter_id"] is None
    assert queue["patient_id"] == 1 and queue["visit_id"] is None and queue["encounter_id"] is None
    remove_source.rollback()
    child.rollback()

    # A complete authorized transfer, including sourced appointment and
    # queue, remains atomic. SQLite's immediate guards require detaching all
    # dependent links before changing any patient id; PostgreSQL defers the
    # composite checks until the transaction has updated the full group.
    group_transfer = conn.begin_nested()
    conn.execute(text("UPDATE appointments SET encounter_id=:id, source_visit_id=1 WHERE id=1"), {"id": e1})
    conn.execute(text("UPDATE queue_entries SET encounter_id=:id WHERE id=1"), {"id": e1})
    if conn.dialect.name == "sqlite":
        conn.execute(text("UPDATE appointments SET source_visit_id=NULL,encounter_id=NULL WHERE id=1"))
        conn.execute(text("UPDATE queue_entries SET visit_id=NULL,encounter_id=NULL WHERE id=1"))
        conn.execute(text("UPDATE visits SET encounter_id=NULL WHERE id=1"))
    conn.execute(text("UPDATE encounters SET patient_id=2 WHERE id=:id"), {"id": e1})
    conn.execute(text("UPDATE visits SET patient_id=2 WHERE id=1"))
    conn.execute(text("UPDATE appointments SET patient_id=2 WHERE id=1"))
    conn.execute(text("UPDATE queue_entries SET patient_id=2 WHERE id=1"))
    if conn.dialect.name == "sqlite":
        conn.execute(text("UPDATE visits SET encounter_id=:id WHERE id=1"), {"id": e1})
        conn.execute(text("UPDATE appointments SET source_visit_id=1,encounter_id=:id WHERE id=1"), {"id": e1})
        conn.execute(text("UPDATE queue_entries SET visit_id=1,encounter_id=:id WHERE id=1"), {"id": e1})
    _flush_deferred(conn)
    assert _visit(conn, 1)["patient_id"] == 2 and _visit(conn, 1)["encounter_id"] == e1
    assert conn.execute(text("SELECT patient_id FROM appointments WHERE id=1")).scalar_one() == 2
    assert conn.execute(text("SELECT patient_id FROM queue_entries WHERE id=1")).scalar_one() == 2
    group_transfer.rollback()
    assert _visit(conn, 1)["patient_id"] == 1 and _visit(conn, 1)["encounter_id"] == e1
    assert conn.execute(text("SELECT patient_id FROM appointments WHERE id=1")).scalar_one() == 1
    assert conn.execute(text("SELECT patient_id FROM queue_entries WHERE id=1")).scalar_one() == 1

    # Explicit encounter anonymization detaches queue-only links and keeps the
    # queue row. FK-driven patient deletion performs the same operation.
    def seed_queue_only(patient_id, queue_id):
        encounter_id = conn.execute(text("INSERT INTO encounters (patient_id,provenance) VALUES (:patient,'new') RETURNING id"), {"patient": patient_id}).scalar_one()
        conn.execute(text("UPDATE queue_entries SET encounter_id=:enc WHERE id=:id"), {"enc": encounter_id, "id": queue_id})
        return encounter_id

    anonymous = conn.begin_nested()
    queue_only = seed_queue_only(1, 3)
    conn.execute(text("UPDATE encounters SET patient_id=NULL WHERE id=:id"), {"id": queue_only})
    row = conn.execute(text("SELECT patient_id,provenance FROM encounters WHERE id=:id"), {"id": queue_only}).mappings().one()
    assert row["patient_id"] is None and row["provenance"] == "legacy_unresolved"
    queue = conn.execute(text("SELECT patient_id,encounter_id FROM queue_entries WHERE id=3")).mappings().one()
    assert queue["patient_id"] == 1 and queue["encounter_id"] is None
    anonymous.rollback()

    patient_delete = conn.begin_nested()
    queue_only = seed_queue_only(3, 4)
    conn.execute(text("DELETE FROM patients WHERE id=3"))
    row = conn.execute(text("SELECT patient_id,provenance FROM encounters WHERE id=:id"), {"id": queue_only}).mappings().one()
    assert row["patient_id"] is None and row["provenance"] == "legacy_unresolved"
    queue = conn.execute(text("SELECT patient_id,encounter_id FROM queue_entries WHERE id=4")).mappings().one()
    assert queue["patient_id"] is None and queue["encounter_id"] is None
    patient_delete.rollback()

    # PG supports a deferred parent/child transfer. SQLite checks immediately,
    # so authorized callers must detach then reattach within ONE transaction.
    transfer = conn.begin_nested()
    if conn.dialect.name == "sqlite":
        conn.execute(text("UPDATE visits SET encounter_id=NULL WHERE id=1"))
    conn.execute(text("UPDATE encounters SET patient_id=2 WHERE id=:id"), {"id": e1})
    conn.execute(text("UPDATE visits SET patient_id=2 WHERE id=1"))
    if conn.dialect.name == "sqlite":
        conn.execute(text("UPDATE visits SET encounter_id=:id WHERE id=1"), {"id": e1})
    _flush_deferred(conn)
    assert _visit(conn, 1)["patient_id"] == 2 and _visit(conn, 1)["encounter_id"] == e1
    transfer.rollback()
    assert _visit(conn, 1)["patient_id"] == 1 and _visit(conn, 1)["encounter_id"] == e1
    assert _visit(conn, 1)["repeat_proof_generation"] == before["repeat_proof_generation"]

    def new_group():
        conn.execute(text("INSERT INTO encounters (patient_id,provenance) VALUES (1,'registrar_cart')"))
    _assert_downgrade_blocked(conn, migration, new_group)

    def grouped():
        conn.execute(text("UPDATE visits SET encounter_id=:id WHERE id=2"), {"id": e1})
    _assert_downgrade_blocked(conn, migration, grouped)

    def orphaned():
        conn.execute(text("DELETE FROM visits WHERE id=2"))
    _assert_downgrade_blocked(conn, migration, orphaned)

    def unknown_new_visit():
        conn.execute(text("INSERT INTO visits (id,patient_id,status) VALUES (6,1,'open')"))
    _assert_downgrade_blocked(conn, migration, unknown_new_visit)

    def corrected_old_patient():
        conn.execute(text("INSERT INTO patients (id,phone) VALUES (999,'synthetic')"))
    _assert_downgrade_blocked(conn, migration, corrected_old_patient)

    def dependent_ledger():
        conn.execute(text("CREATE TABLE synthetic_ledger (encounter_id INTEGER REFERENCES encounters(id))"))
        conn.execute(text("INSERT INTO synthetic_ledger (encounter_id) VALUES (:id)"), {"id": e1})
    _assert_downgrade_blocked(conn, migration, dependent_ledger)

    old_gen = rows[0]["generation"]
    migration.downgrade()
    assert "encounter_id" not in _visit(conn, 1)
    # Existing repeat/confirmation triggers survived the SQLite column drop.
    conn.execute(text("UPDATE visits SET patient_id=2 WHERE id=1"))
    assert _visit(conn, 1)["repeat_proof_generation"] is None
    conn.execute(text("UPDATE visits SET patient_id=1 WHERE id=1"))
    migration.upgrade()
    regenerated = conn.execute(text("SELECT generation FROM encounters WHERE legacy_visit_id=1")).scalar_one()
    assert regenerated != old_gen
    assert _visit(conn, 4)["encounter_id"] is None and _visit(conn, 5)["encounter_id"] is None


def test_sqlite_migrated_encounters():
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
        dbapi_conn.execute("PRAGMA recursive_triggers=ON")

    try:
        with engine.begin() as conn:
            _exercise(conn)
    finally:
        engine.dispose()


def test_orm_metadata_accepts_new_group_and_rejects_foreign_patient():
    # Runtime writers construct Encounter through ORM rather than SQL. Keep a
    # metadata-only smoke test in addition to the actual migration tests.
    import app.db.base  # noqa: F401
    from app.db.base_class import Base
    from app.models.encounter import Encounter
    from app.models.patient import Patient
    from app.models.visit import Visit

    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")

    try:
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as db:
            first = Patient(first_name="Synthetic", last_name="One")
            second = Patient(first_name="Synthetic", last_name="Two")
            db.add_all([first, second])
            db.flush()
            encounter = Encounter(patient_id=first.id, provenance="new")
            db.add(encounter)
            db.flush()
            assert encounter.generation > 0
            db.add_all([
                Visit(patient_id=first.id, encounter_id=encounter.id, status="open"),
                Visit(patient_id=first.id, encounter_id=encounter.id, status="open"),
            ])
            db.commit()
            assert db.query(Visit).filter_by(encounter_id=encounter.id).count() == 2
            db.add(Visit(patient_id=second.id, encounter_id=encounter.id, status="open"))
            with pytest.raises(DBAPIError):
                db.commit()
            db.rollback()
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgres_migrated_encounters():
    raw = os.environ.get("DATABASE_URL", "").strip()
    ci = os.environ.get("CI", "").lower() == "true"
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_encounters_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000"})
    try:
        with engine.begin() as conn:
            _exercise(conn)
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture(params=["sqlite", "postgresql"])
def isolation_engine(request, tmp_path):
    schema, admin = None, None
    if request.param == "sqlite":
        engine = create_engine(f"sqlite:///{tmp_path / 'encounter-isolation.sqlite'}", connect_args={"check_same_thread": False})

        @event.listens_for(engine, "connect")
        def _enable_fks(dbapi_conn, _record):
            dbapi_conn.execute("PRAGMA foreign_keys=ON")
            dbapi_conn.execute("PRAGMA recursive_triggers=ON")
    else:
        raw = os.environ.get("DATABASE_URL", "").strip()
        ci = os.environ.get("CI", "").lower() == "true"
        if not raw or make_url(raw).get_backend_name() != "postgresql":
            if ci:
                pytest.fail("CI requires PostgreSQL DATABASE_URL")
            pytest.skip("requires disposable PostgreSQL DATABASE_URL")
        url = make_url(raw)
        if not ci and not (url.database or "").startswith("clinic_test"):
            pytest.skip("use an explicitly disposable clinic_test database")
        schema = "test_encounters_isolation_" + uuid.uuid4().hex
        admin = create_engine(url)
        with admin.begin() as conn:
            conn.execute(CreateSchema(schema))
        engine = create_engine(url, pool_size=5, connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"})
    try:
        with engine.begin() as conn:
            _setup_0103(conn)
            migration = _migration("0104_encounters.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
        yield engine
    finally:
        engine.dispose()
        if admin is not None:
            with admin.begin() as conn:
                conn.execute(DropSchema(schema, cascade=True))
            admin.dispose()


@pytest.mark.parametrize("kind", ["queue_null", "encounter_null", "patient_delete"])
@pytest.mark.parametrize("commit", [True, False])
def test_anonymization_is_atomic_to_other_connections(isolation_engine, kind, commit):
    """Neither direct NULL nor FK-driven deletion leaks an intermediate state."""
    engine = isolation_engine
    patient_id, queue_id = (3, 4) if kind == "patient_delete" else (1, 3)
    with engine.begin() as conn:
        encounter_id = conn.execute(text("INSERT INTO encounters (patient_id,provenance) VALUES (:patient,'new') RETURNING id"), {"patient": patient_id}).scalar_one()
        conn.execute(text("UPDATE queue_entries SET encounter_id=:enc WHERE id=:id"), {"enc": encounter_id, "id": queue_id})

    updated, release = threading.Event(), threading.Event()

    def mutate():
        with engine.connect() as conn:
            transaction = conn.begin()
            try:
                if kind == "queue_null":
                    conn.execute(text("UPDATE queue_entries SET patient_id=NULL WHERE id=:id"), {"id": queue_id})
                elif kind == "encounter_null":
                    conn.execute(text("UPDATE encounters SET patient_id=NULL WHERE id=:id"), {"id": encounter_id})
                else:
                    conn.execute(text("DELETE FROM patients WHERE id=:id"), {"id": patient_id})
                updated.set()
                assert release.wait(10)
                if commit:
                    transaction.commit()
                else:
                    transaction.rollback()
            except BaseException:
                transaction.rollback()
                raise

    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(mutate)
        try:
            assert updated.wait(10)
            # A different transaction sees the complete old state while the
            # writer holds an uncommitted, already-triggered update.
            with engine.connect() as reader:
                queue = reader.execute(text("SELECT patient_id,encounter_id FROM queue_entries WHERE id=:id"), {"id": queue_id}).mappings().one()
                encounter = reader.execute(text("SELECT patient_id,provenance FROM encounters WHERE id=:id"), {"id": encounter_id}).mappings().one()
                assert queue["patient_id"] == patient_id and queue["encounter_id"] == encounter_id
                assert encounter["patient_id"] == patient_id and encounter["provenance"] == "new"
        finally:
            release.set()
        future.result(timeout=15)

    with engine.connect() as reader:
        queue = reader.execute(text("SELECT patient_id,encounter_id FROM queue_entries WHERE id=:id"), {"id": queue_id}).mappings().one()
        encounter = reader.execute(text("SELECT patient_id,provenance FROM encounters WHERE id=:id"), {"id": encounter_id}).mappings().one()
        if not commit:
            assert queue["patient_id"] == patient_id and queue["encounter_id"] == encounter_id
            assert encounter["patient_id"] == patient_id and encounter["provenance"] == "new"
        elif kind == "queue_null":
            assert queue["patient_id"] is None and queue["encounter_id"] is None
            assert encounter["patient_id"] == patient_id and encounter["provenance"] == "new"
        else:
            assert queue["encounter_id"] is None
            assert queue["patient_id"] == (None if kind == "patient_delete" else patient_id)
            assert encounter["patient_id"] is None and encounter["provenance"] == "legacy_unresolved"


@pytest.mark.parametrize("child_kind", ["appointment", "queue"])
def test_postgres_child_commit_waits_and_revalidates_visit_group(isolation_engine, child_kind):
    """A stale source claim cannot commit after its Visit moves to another group."""
    engine = isolation_engine
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL deferred-FK lock proof; SQLite checks immediately")
    with engine.connect() as conn:
        old_encounter = _visit(conn, 1)["encounter_id"]
        new_encounter = _visit(conn, 2)["encounter_id"]
    started, worker_pid = threading.Event(), []

    def claim_old_group():
        try:
            with engine.begin() as conn:
                worker_pid.append(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
                started.set()
                if child_kind == "appointment":
                    conn.execute(text("UPDATE appointments SET source_visit_id=1, encounter_id=:id WHERE id=1"), {"id": old_encounter})
                else:
                    conn.execute(text("UPDATE queue_entries SET encounter_id=:id WHERE id=1"), {"id": old_encounter})
                conn.execute(text("SET CONSTRAINTS ALL IMMEDIATE"))
            return True
        except DBAPIError:
            return False

    with engine.connect() as holder:
        transaction = holder.begin()
        holder.execute(text("UPDATE visits SET encounter_id=:id WHERE id=1"), {"id": new_encounter})
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(claim_old_group)
            try:
                assert started.wait(5)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline:
                    assert not future.done(), "source claim did not wait for the Visit row"
                    with engine.connect() as inspector:
                        blocked = inspector.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": worker_pid[0]}).scalar_one()
                    if blocked:
                        break
                    time.sleep(0.02)
                else:
                    pytest.fail("source claim did not block on the competing Visit change")
            finally:
                transaction.commit()
            assert future.result(timeout=15) is False

    with engine.connect() as conn:
        assert _visit(conn, 1)["encounter_id"] == new_encounter
        table = "appointments" if child_kind == "appointment" else "queue_entries"
        assert conn.execute(text(f"SELECT encounter_id FROM {table} WHERE id=1")).scalar_one() is None
        if child_kind == "appointment":
            assert conn.execute(text("SELECT source_visit_id FROM appointments WHERE id=1")).scalar_one() is None


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
def test_offline_upgrade_and_downgrade_render(dialect):
    output = io.StringIO()
    ctx = MigrationContext.configure(url=f"{dialect}://", opts={"as_sql": True, "output_buffer": output})
    migration = _migration("0104_encounters.py")
    migration.op = Operations(ctx)
    migration.upgrade()
    migration.downgrade()
    sql = output.getvalue().lower()
    assert "encounters" in sql and "legacy_unresolved" in sql
    assert "encounter_downgrade" in sql or "would destroy grouping history" in sql

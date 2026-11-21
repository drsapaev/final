"""Exercise actual 0103 evidence triggers on SQLite and disposable PG.

The fixtures include the preceding 0102 confirmation triggers so the test
checks their interaction as well as the repeat-evidence fence. No historical
row is interpreted as having completed a consultation by the migration.
"""

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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.schema import CreateSchema, DropSchema

_VERSIONS = Path(__file__).resolve().parents[2] / "alembic/versions"


def _migration(filename):
    spec = importlib.util.spec_from_file_location(filename.removesuffix(".py"), _VERSIONS / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _setup_0102(conn):
    conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    conn.execute(text("INSERT INTO users (id) VALUES (1), (2)"))
    conn.execute(text("CREATE TABLE doctors (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id) ON DELETE SET NULL)"))
    conn.execute(text("INSERT INTO doctors (id, user_id) VALUES (10, 1), (11, NULL)"))
    conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, phone VARCHAR(64))"))
    conn.execute(text("INSERT INTO patients (id, phone) VALUES (1, 'synthetic'), (2, 'synthetic')"))
    conn.execute(text("""
        CREATE TABLE visits (
          id INTEGER PRIMARY KEY, patient_id INTEGER NOT NULL REFERENCES patients(id),
          doctor_id INTEGER REFERENCES doctors(id) ON DELETE SET NULL,
          visit_date DATE, visit_time VARCHAR(8), department VARCHAR(64), department_id INTEGER,
          discount_mode VARCHAR(32), confirmation_channel VARCHAR(16), status VARCHAR(32) NOT NULL,
          confirmation_token VARCHAR(128), confirmation_expires_at TIMESTAMP,
          reminder_sent_at TIMESTAMP, reminder_generation INTEGER NOT NULL DEFAULT 0,
          reminder_claimed_at TIMESTAMP
        )
    """))
    conn.execute(text("""
        CREATE TABLE visit_services (
          id INTEGER PRIMARY KEY, visit_id INTEGER NOT NULL REFERENCES visits(id) ON DELETE CASCADE, service_id INTEGER,
          code VARCHAR(64), name VARCHAR(255), duration_minutes_snapshot INTEGER,
          qty INTEGER, price NUMERIC(12,2), currency VARCHAR(8)
        )
    """))
    conn.execute(text("""
        INSERT INTO visits (id, patient_id, doctor_id, visit_date, status)
        VALUES (1, 1, 10, '2031-04-01', 'completed'),
               (2, 1, 10, '2031-04-01', 'closed')
    """))
    context = _migration("0102_visit_confirmation_context.py")
    context.op = Operations(MigrationContext.configure(conn))
    context.upgrade()


def _row(conn, visit_id=1):
    return conn.execute(text("SELECT * FROM visits WHERE id=:id"), {"id": visit_id}).mappings().one()


def _record(conn, visit_id=1, *, consulted=True, user_id=1):
    conn.execute(text("""
        UPDATE visits SET repeat_proof_generation=repeat_evidence_generation,
          repeat_proof_consultation=:consulted, repeat_proof_doctor_user_id=:user_id
        WHERE id=:id
    """), {"id": visit_id, "consulted": consulted, "user_id": user_id})
    row = _row(conn, visit_id)
    assert row["repeat_proof_generation"] == row["repeat_evidence_generation"]
    return row["repeat_evidence_generation"]


def _invalidated(conn, previous, visit_id=1):
    row = _row(conn, visit_id)
    assert row["repeat_evidence_generation"] > previous
    assert row["repeat_proof_generation"] is None
    assert row["repeat_proof_consultation"] is None
    assert row["repeat_proof_doctor_user_id"] is None


def _exercise(conn):
    _setup_0102(conn)
    migration = _migration("0103_visit_consultation_completion.py")
    migration.op = Operations(MigrationContext.configure(conn))
    migration.upgrade()
    for visit_id in (1, 2):
        row = _row(conn, visit_id)
        assert row["repeat_evidence_generation"] > 2**52
        assert row["repeat_proof_generation"] is None
        assert row["repeat_proof_consultation"] is None
        assert row["repeat_proof_doctor_user_id"] is None
        assert row["repeat_assigned_doctor_user_id"] is None
        assert row["repeat_assigned_owner_generation"] is None

    # Newly assigned preclinical visits capture a stable human owner. Merely
    # importing an already in-progress/completed/closed record does not prove
    # who was assigned at the beginning of that encounter.
    for visit_id, status in ((4, "open"), (5, "pending_confirmation"),
                             (6, "in_progress"), (7, "completed"), (8, "closed")):
        conn.execute(text("""
            INSERT INTO visits (id, patient_id, doctor_id, visit_date, status)
            VALUES (:id, 1, 10, '2031-04-01', :status)
        """), {"id": visit_id, "status": status})
    owner_generation = conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=10")).scalar_one()
    for visit_id in (4, 5):
        assert _row(conn, visit_id)["repeat_assigned_doctor_user_id"] == 1
        assert _row(conn, visit_id)["repeat_assigned_owner_generation"] == owner_generation
    for visit_id in (6, 7, 8):
        assert _row(conn, visit_id)["repeat_assigned_doctor_user_id"] is None
        assert _row(conn, visit_id)["repeat_assigned_owner_generation"] is None

    conn.execute(text("UPDATE doctors SET user_id=user_id WHERE id=10"))
    assert conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=10")).scalar_one() == owner_generation
    assert _row(conn, 4)["repeat_assigned_owner_generation"] == owner_generation
    conn.execute(text("INSERT INTO doctors (id, user_id, repeat_owner_generation) VALUES (12,NULL,42)"))
    assert conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=12")).scalar_one() != 42

    # Rebinding A -> B -> A never revives in-flight assignments. Historical
    # completed proof remains bound to the originally attested human.
    _record(conn, 7, user_id=1)
    first_generation = owner_generation
    conn.execute(text("UPDATE doctors SET user_id=2 WHERE id=10"))
    second_generation = conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=10")).scalar_one()
    assert second_generation != first_generation
    for visit_id in (4, 5):
        assert _row(conn, visit_id)["repeat_assigned_doctor_user_id"] is None
        assert _row(conn, visit_id)["repeat_assigned_owner_generation"] is None
    assert _row(conn, 7)["repeat_proof_doctor_user_id"] == 1
    conn.execute(text("UPDATE doctors SET user_id=1 WHERE id=10"))
    owner_generation = conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=10")).scalar_one()
    assert owner_generation not in (first_generation, second_generation)
    assert _row(conn, 4)["repeat_assigned_doctor_user_id"] is None
    assert _row(conn, 7)["repeat_proof_doctor_user_id"] == 1

    # Rollback of a relink must restore the previous epoch and assignments.
    conn.execute(text("""
        INSERT INTO visits (id, patient_id, doctor_id, visit_date, status)
        VALUES (9, 1, 10, '2031-04-01', 'open')
    """))
    nested = conn.begin_nested()
    conn.execute(text("UPDATE doctors SET user_id=2 WHERE id=10"))
    assert _row(conn, 9)["repeat_assigned_doctor_user_id"] is None
    nested.rollback()
    assert _row(conn, 9)["repeat_assigned_doctor_user_id"] == 1
    assert _row(conn, 9)["repeat_assigned_owner_generation"] == owner_generation

    # Only a preclinical reassignment establishes new owner provenance.
    conn.execute(text("UPDATE visits SET doctor_id=NULL WHERE id IN (5,6,7)"))
    conn.execute(text("UPDATE visits SET doctor_id=10 WHERE id IN (5,6,7)"))
    assert _row(conn, 5)["repeat_assigned_doctor_user_id"] == 1
    assert _row(conn, 5)["repeat_assigned_owner_generation"] == owner_generation
    for visit_id in (6, 7):
        assert _row(conn, visit_id)["repeat_assigned_doctor_user_id"] is None
        assert _row(conn, visit_id)["repeat_assigned_owner_generation"] is None

    # Direct generation writes cannot resurrect a previous owner generation.
    if conn.dialect.name == "sqlite":
        with pytest.raises(SQLAlchemyError), conn.begin_nested():
            conn.execute(text("UPDATE doctors SET repeat_owner_generation=:old WHERE id=10"), {"old": first_generation})
    else:
        conn.execute(text("UPDATE doctors SET repeat_owner_generation=:old WHERE id=10"), {"old": first_generation})
    observed_generation = conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=10")).scalar_one()
    if conn.dialect.name == "postgresql":
        assert observed_generation == owner_generation
        conn.execute(text("UPDATE visits SET repeat_assigned_doctor_user_id=2, repeat_assigned_owner_generation=:gen WHERE id=5"), {"gen": first_generation})
        assert _row(conn, 5)["repeat_assigned_doctor_user_id"] == 1
        assert _row(conn, 5)["repeat_assigned_owner_generation"] == owner_generation
    else:
        assert observed_generation == owner_generation
        assert _row(conn, 5)["repeat_assigned_doctor_user_id"] == 1

    # Even if inserted with caller-supplied proof, a newly created visit does
    # not start with manufactured completion evidence.
    conn.execute(text("""
        INSERT INTO visits (id, patient_id, doctor_id, visit_date, status,
          repeat_evidence_generation, repeat_proof_generation,
          repeat_proof_consultation, repeat_proof_doctor_user_id,
          repeat_assigned_doctor_user_id, repeat_assigned_owner_generation)
        VALUES (3, 1, 10, '2031-04-01', 'completed', 42, 42, true, 1, 1, 42)
    """))
    inserted = _row(conn, 3)
    assert inserted["repeat_evidence_generation"] != 42
    assert inserted["repeat_proof_generation"] is None
    assert inserted["repeat_proof_consultation"] is None
    assert inserted["repeat_proof_doctor_user_id"] is None
    assert inserted["repeat_assigned_doctor_user_id"] is None
    assert inserted["repeat_assigned_owner_generation"] is None

    conn.execute(text("INSERT INTO visit_services (id,visit_id,service_id,name,qty,price) VALUES (1,1,9,'synthetic',1,100)"))
    original = _record(conn)
    _record(conn, 2, consulted=False)
    conn.execute(text("UPDATE visits SET patient_id=patient_id, doctor_id=doctor_id, visit_date=visit_date WHERE id=1"))
    conn.execute(text("UPDATE visits SET status='closed' WHERE id=1"))
    conn.execute(text("UPDATE visits SET status='completed' WHERE id=1"))
    conn.execute(text("UPDATE visits SET visit_time='11:30' WHERE id=1"))
    conn.execute(text("UPDATE visit_services SET price=120, name='renamed', qty=qty, service_id=service_id WHERE id=1"))
    row = _row(conn)
    assert row["repeat_evidence_generation"] == original
    assert row["repeat_proof_generation"] == original
    assert bool(row["repeat_proof_consultation"]) is True

    # Every identity and clinical mutation must fence the previous proof,
    # including A -> B -> A, while unrelated financial changes do not.
    for column, value, restore in (("patient_id", 2, 1), ("doctor_id", 11, 10),
                                   ("visit_date", "2031-04-02", "2031-04-01")):
        prior = _record(conn)
        conn.execute(text(f"UPDATE visits SET {column}=:value WHERE id=1"), {"value": value})
        _invalidated(conn, prior)
        changed = _row(conn)["repeat_evidence_generation"]
        conn.execute(text(f"UPDATE visits SET {column}=:value WHERE id=1"), {"value": restore})
        _invalidated(conn, changed)
        assert _row(conn)["repeat_evidence_generation"] != prior

    prior = _record(conn)
    conn.execute(text("UPDATE visits SET status='in_progress' WHERE id=1"))
    _invalidated(conn, prior)
    conn.execute(text("UPDATE visits SET status='completed' WHERE id=1"))
    assert _row(conn)["repeat_proof_generation"] is None

    # A change to a service fences the proof for both the old and new owner.
    for sql in (
        "UPDATE visit_services SET qty=2 WHERE id=1",
        "UPDATE visit_services SET service_id=10 WHERE id=1",
    ):
        prior = _record(conn)
        conn.execute(text(sql))
        _invalidated(conn, prior)
    old_gen = _record(conn)
    new_gen = _record(conn, 2)
    nested = conn.begin_nested()
    conn.execute(text("UPDATE visit_services SET visit_id=2 WHERE id=1"))
    _invalidated(conn, old_gen)
    _invalidated(conn, new_gen, 2)
    nested.rollback()
    assert _row(conn)["repeat_proof_generation"] == old_gen
    assert _row(conn, 2)["repeat_proof_generation"] == new_gen
    conn.execute(text("UPDATE visit_services SET visit_id=2 WHERE id=1"))
    _invalidated(conn, old_gen)
    _invalidated(conn, new_gen, 2)
    old_gen = _record(conn, 2)
    conn.execute(text("DELETE FROM visit_services WHERE id=1"))
    _invalidated(conn, old_gen, 2)
    old_gen = _record(conn, 2)
    conn.execute(text("INSERT INTO visit_services (id,visit_id,service_id,name,qty,price) VALUES (2,2,9,'synthetic',1,100)"))
    _invalidated(conn, old_gen, 2)

    # Normal parent deletion must remain possible: the child cascade invokes
    # both the pre-existing confirmation and new evidence triggers.
    conn.execute(text("INSERT INTO visits (id,patient_id,doctor_id,visit_date,status) VALUES (15,1,10,'2031-04-01','open')"))
    conn.execute(text("INSERT INTO visit_services (id,visit_id,service_id,name,qty,price) VALUES (15,15,9,'synthetic',1,100)"))
    conn.execute(text("DELETE FROM visits WHERE id=15"))
    assert conn.execute(text("SELECT COUNT(*) FROM visit_services WHERE id=15")).scalar_one() == 0

    # Direct generation writes cannot restore an old valid snapshot. PG
    # preserves the generation; SQLite clears the proof on such a change.
    old_gen = _record(conn)
    if conn.dialect.name == "postgresql":
        conn.execute(text("UPDATE visits SET repeat_evidence_generation=42 WHERE id=1"))
        assert _row(conn)["repeat_evidence_generation"] == old_gen
        assert _row(conn)["repeat_proof_generation"] == old_gen
    else:
        with pytest.raises(SQLAlchemyError), conn.begin_nested():
            conn.execute(text("UPDATE visits SET repeat_evidence_generation=42 WHERE id=1"))
        assert _row(conn)["repeat_proof_generation"] == old_gen

    # A deleted doctor user cannot leave an apparently matching identity.
    _record(conn, 3, user_id=2)
    conn.execute(text("INSERT INTO doctors (id, user_id) VALUES (13,2)"))
    conn.execute(text("""
        INSERT INTO visits (id, patient_id, doctor_id, visit_date, status)
        VALUES (10,1,13,'2031-04-01','open')
    """))
    assert _row(conn, 10)["repeat_assigned_doctor_user_id"] == 2
    before_delete_owner = conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=13")).scalar_one()
    conn.execute(text("DELETE FROM users WHERE id=2"))
    assert _row(conn, 3)["repeat_proof_doctor_user_id"] is None
    assert _row(conn, 10)["repeat_assigned_doctor_user_id"] is None
    assert _row(conn, 10)["repeat_assigned_owner_generation"] is None
    assert conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=13")).scalar_one() != before_delete_owner

    # Repeating the same PostgreSQL PRNG seed cannot reproduce a generation,
    # including across deletion/reuse of both Visit and Doctor identifiers.
    if conn.dialect.name == "postgresql":
        conn.execute(text("SELECT pg_catalog.setseed(0.5)"))
    conn.execute(text("INSERT INTO doctors (id,user_id) VALUES (30,NULL)"))
    first_doctor = conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=30")).scalar_one()
    conn.execute(text("INSERT INTO visits (id,patient_id,doctor_id,visit_date,status) VALUES (30,1,30,'2031-04-01','completed')"))
    first_visit = _row(conn, 30)["repeat_evidence_generation"]
    conn.execute(text("DELETE FROM visits WHERE id=30"))
    conn.execute(text("DELETE FROM doctors WHERE id=30"))
    if conn.dialect.name == "postgresql":
        conn.execute(text("SELECT pg_catalog.setseed(0.5)"))
    conn.execute(text("INSERT INTO doctors (id,user_id) VALUES (30,NULL)"))
    conn.execute(text("INSERT INTO visits (id,patient_id,doctor_id,visit_date,status) VALUES (30,1,30,'2031-04-01','completed')"))
    assert conn.execute(text("SELECT repeat_owner_generation FROM doctors WHERE id=30")).scalar_one() > first_doctor
    assert _row(conn, 30)["repeat_evidence_generation"] > first_visit

    if conn.dialect.name == "sqlite":
        for sql in ("UPDATE repeat_evidence_generation_clock SET value=value-1",
                    "DELETE FROM repeat_evidence_generation_clock",
                    "INSERT OR REPLACE INTO repeat_evidence_generation_clock VALUES (1,4503599627370496)"):
            with pytest.raises(SQLAlchemyError), conn.begin_nested():
                conn.execute(text(sql))

    previous = _record(conn)
    with pytest.raises(SQLAlchemyError), conn.begin_nested():
        migration.downgrade()
    assert _row(conn)["repeat_proof_generation"] == previous
    conn.execute(text("DELETE FROM visit_services"))
    conn.execute(text("DELETE FROM visits WHERE id <> 1"))
    conn.execute(text("""
        UPDATE visits SET repeat_proof_generation=NULL, repeat_proof_consultation=NULL,
          repeat_proof_doctor_user_id=NULL WHERE id=1
    """))
    migration.downgrade()
    migration.upgrade()
    row = _row(conn)
    assert row["repeat_evidence_generation"] != previous
    assert row["repeat_proof_generation"] is None
    assert row["repeat_proof_consultation"] is None
    assert row["repeat_proof_doctor_user_id"] is None
    assert row["repeat_assigned_doctor_user_id"] is None
    assert row["repeat_assigned_owner_generation"] is None


@pytest.mark.parametrize("recursive_triggers", ["ON", "OFF"])
def test_sqlite_migrated_completion_evidence(recursive_triggers):
    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def _enable_fks(dbapi_conn, _record):
        dbapi_conn.execute("PRAGMA foreign_keys=ON")
        dbapi_conn.execute(f"PRAGMA recursive_triggers={recursive_triggers}")

    try:
        with engine.begin() as conn:
            _exercise(conn)
    finally:
        engine.dispose()


@pytest.mark.integration
def test_postgres_migrated_completion_evidence():
    raw = os.environ.get("DATABASE_URL", "").strip()
    ci = os.environ.get("CI", "").lower() == "true"
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_visit_repeat_" + uuid.uuid4().hex
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


@pytest.mark.integration
def test_postgres_service_change_waits_for_completion_then_fences_proof():
    raw = os.environ.get("DATABASE_URL", "").strip()
    ci = os.environ.get("CI", "").lower() == "true"
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_visit_repeat_race_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(
        url, pool_size=5,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
    )
    try:
        with engine.begin() as conn:
            _setup_0102(conn)
            migration = _migration("0103_visit_consultation_completion.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            conn.execute(text("INSERT INTO visit_services (id,visit_id,service_id,name,qty,price) VALUES (1,1,9,'synthetic',1,100)"))

        started = threading.Event()
        worker_pid = []

        def change_service():
            with engine.begin() as conn:
                worker_pid.append(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
                started.set()
                conn.execute(text("UPDATE visit_services SET qty=2 WHERE id=1"))

        # Completion owns Visit before reading child rows and saving proof.
        # The concurrent row change waits in its trigger, then invalidates the
        # just-committed proof in the same transaction as the child update.
        with engine.connect() as holder:
            transaction = holder.begin()
            holder.execute(text("SELECT id FROM visits WHERE id=1 FOR UPDATE"))
            recorded = _record(holder)
            with ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(change_service)
                try:
                    assert started.wait(5)
                    deadline = time.monotonic() + 10
                    while time.monotonic() < deadline:
                        assert not future.done(), "child change failed to wait for Visit lock"
                        with engine.connect() as inspector:
                            blocked = inspector.execute(
                                text("SELECT cardinality(pg_blocking_pids(:pid))"),
                                {"pid": worker_pid[0]},
                            ).scalar_one()
                        if blocked:
                            break
                        time.sleep(0.02)
                    else:
                        pytest.fail("child write did not wait on the completion Visit lock")
                finally:
                    transaction.commit()
                future.result(timeout=15)

        with engine.connect() as conn:
            _invalidated(conn, recorded)
            assert conn.execute(text("SELECT qty FROM visit_services WHERE id=1")).scalar_one() == 2
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def owner_pg_engine():
    raw = os.environ.get("DATABASE_URL", "").strip()
    ci = os.environ.get("CI", "").lower() == "true"
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        if ci:
            pytest.fail("CI requires PostgreSQL DATABASE_URL")
        pytest.skip("requires disposable PostgreSQL DATABASE_URL")
    url = make_url(raw)
    if not ci and not (url.database or "").startswith("clinic_test"):
        pytest.skip("use an explicitly disposable clinic_test database")
    schema = "test_visit_repeat_owner_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(
        url, pool_size=5,
        connect_args={"options": f"-csearch_path={schema} -cstatement_timeout=15000 -clock_timeout=10000"},
    )
    try:
        with engine.begin() as conn:
            _setup_0102(conn)
            migration = _migration("0103_visit_consultation_completion.py")
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            conn.execute(text("""
                INSERT INTO visits (id, patient_id, doctor_id, visit_date, status)
                VALUES (4,1,10,'2031-04-01','open')
            """))
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def _wait_for_block(engine, started, worker_pid, future):
    assert started.wait(5)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        assert not future.done(), "operation failed to wait for the competing Visit lock"
        with engine.connect() as conn:
            if conn.execute(text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": worker_pid[0]}).scalar_one():
                return
        time.sleep(0.02)
    pytest.fail("operation did not wait on the competing Visit lock")


@pytest.mark.integration
def test_postgres_rebind_waits_for_completion_and_preserves_earlier_proof(owner_pg_engine):
    engine = owner_pg_engine
    started, worker_pid = threading.Event(), []

    def rebind():
        with engine.begin() as conn:
            worker_pid.append(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            conn.execute(text("UPDATE doctors SET user_id=2 WHERE id=10"))

    # Completion owns the Visit and records A's actual assignment first.
    # The rebind cannot pass that Visit until completion commits; the recheck
    # then sees completed, and must not destroy A's historical proof.
    with engine.connect() as holder:
        transaction = holder.begin()
        holder.execute(text("SELECT id FROM visits WHERE id=4 FOR UPDATE"))
        assert _row(holder, 4)["repeat_assigned_doctor_user_id"] == 1
        holder.execute(text("UPDATE visits SET status='completed' WHERE id=4"))
        generation = _record(holder, 4, user_id=1)
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(rebind)
            try:
                _wait_for_block(engine, started, worker_pid, future)
            finally:
                transaction.commit()
            future.result(timeout=15)
    with engine.connect() as conn:
        row = _row(conn, 4)
        assert row["status"] == "completed"
        assert row["repeat_proof_doctor_user_id"] == 1
        assert row["repeat_proof_generation"] == generation
        assert conn.execute(text("SELECT user_id FROM doctors WHERE id=10")).scalar_one() == 2


@pytest.mark.integration
def test_postgres_completion_waits_for_rebind_and_observes_invalid_assignment(owner_pg_engine):
    engine = owner_pg_engine
    started, worker_pid = threading.Event(), []

    def read_assignment_under_visit_lock():
        with engine.begin() as conn:
            worker_pid.append(conn.execute(text("SELECT pg_backend_pid()")).scalar_one())
            started.set()
            conn.execute(text("SELECT id FROM visits WHERE id=4 FOR UPDATE"))
            return dict(_row(conn, 4))

    # The rebind invalidates A's in-flight assignment before B's completion
    # can acquire Visit. After commit the completion path must see unknown,
    # never infer that B was originally assigned.
    with engine.connect() as holder:
        transaction = holder.begin()
        holder.execute(text("UPDATE doctors SET user_id=2 WHERE id=10"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(read_assignment_under_visit_lock)
            try:
                _wait_for_block(engine, started, worker_pid, future)
            finally:
                transaction.commit()
            observed = future.result(timeout=15)
    assert observed["repeat_assigned_doctor_user_id"] is None
    assert observed["repeat_assigned_owner_generation"] is None
    assert observed["repeat_proof_generation"] is None


@pytest.mark.integration
@pytest.mark.parametrize("endpoint", ["review", "attest"])
def test_postgres_individual_logout_wins_before_repeat_write(monkeypatch, endpoint):
    """Logout's User lock serializes JTI revocation with the actual endpoint."""
    from datetime import UTC, date, datetime

    import jwt
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    import app.db.base  # noqa: F401
    from app.api.deps import get_db
    from app.api.v1.endpoints import visits as visits_endpoint
    from app.core.config import settings
    from app.db.base_class import Base
    from app.main import app
    from app.models.audit import AuditLog
    from app.models.authentication import TokenBlacklist
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.user import User
    from app.models.visit import Visit
    from tests.conftest import mint_access_token

    raw = os.environ.get("DATABASE_URL", "")
    if not raw or make_url(raw).get_backend_name() != "postgresql":
        pytest.skip("requires disposable PostgreSQL")
    url = make_url(raw)
    if not (url.database or "").startswith("clinic_test") and os.environ.get("CI", "").lower() != "true":
        pytest.skip("requires a disposable clinic_test database")
    schema = "test_repeat_logout_" + uuid.uuid4().hex
    admin_engine = create_engine(url)
    with admin_engine.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"})
    try:
        Base.metadata.create_all(engine)
        with Session(engine, expire_on_commit=False) as db:
            actor = User(username="synthetic-admin", email="admin@invalid.example", full_name="Synthetic",
                         hashed_password="synthetic", role="Admin", is_active=True, is_superuser=True)
            clinician = User(username="synthetic-doctor", email="doctor@invalid.example", full_name="Synthetic",
                             hashed_password="synthetic", role="Doctor", is_active=True)
            patient = Patient(first_name="Synthetic", last_name="Patient")
            db.add_all([actor, clinician, patient])
            db.flush()
            doctor = Doctor(user_id=clinician.id, specialty="cardiology", active=True)
            db.add(doctor)
            db.flush()
            visit = Visit(patient_id=patient.id, doctor_id=doctor.id, visit_date=date(2025, 1, 1),
                          status="completed", discount_mode="none", source="desk", repeat_evidence_generation=101)
            db.add(visit)
            db.commit()
            visit_id, clinician_id, actor_id = visit.id, clinician.id, actor.id
            token = mint_access_token(actor)
        claims = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        headers = {"Authorization": f"Bearer {token}"}

        def session_override():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = session_override
        with TestClient(app) as client:
            review = client.post(f"/api/v1/visits/{visit_id}/repeat-evidence/review", headers=headers,
                                 json={"doctor_user_id": clinician_id})
            assert review.status_code == 200, review.text
            payload = review.json()
            started, worker_pid = threading.Event(), []
            actual_lock = visits_endpoint._lock_repeat_review_context

            def marked_lock(db, bearer, requested_visit_id):
                worker_pid.append(db.execute(text("SELECT pg_backend_pid()")).scalar_one())
                started.set()
                return actual_lock(db, bearer, requested_visit_id)

            monkeypatch.setattr(visits_endpoint, "_lock_repeat_review_context", marked_lock)

            def request_worker():
                if endpoint == "review":
                    return client.post(f"/api/v1/visits/{visit_id}/repeat-evidence/review", headers=headers,
                                       json={"doctor_user_id": clinician_id})
                return client.post(f"/api/v1/visits/{visit_id}/repeat-evidence/attest", headers=headers,
                                   json={"doctor_user_id": clinician_id, "reviewed_record": True,
                                         "expected_generation": payload["evidence_generation"],
                                         "review_expires_at": payload["review_expires_at"], "token": payload["token"]})

            with Session(engine) as logout:
                logout.query(User).filter_by(id=actor_id).with_for_update().one()
                logout.add(TokenBlacklist(jti=claims["jti"], user_id=actor_id,
                                          expires_at=datetime.fromtimestamp(claims["exp"], UTC), reason="logout"))
                logout.flush()
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(request_worker)
                    try:
                        _wait_for_block(engine, started, worker_pid, future)
                    finally:
                        logout.commit()
                    response = future.result(timeout=15)
            assert response.status_code == 401, response.text
            assert "no-store" in response.headers.get("cache-control", "").lower()
        with Session(engine) as db:
            assert db.get(Visit, visit_id).repeat_proof_generation is None
            assert db.query(AuditLog).filter_by(action="repeat_consultation_attested", entity_id=visit_id).count() == 0
    finally:
        app.dependency_overrides.clear()
        engine.dispose()
        with admin_engine.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin_engine.dispose()


@pytest.mark.parametrize("dialect", ["postgresql", "sqlite"])
@pytest.mark.parametrize("direction", ["upgrade", "downgrade"])
def test_offline_migration_requires_live_preflight(dialect, direction):
    output = io.StringIO()
    ctx = MigrationContext.configure(url=f"{dialect}://", opts={"as_sql": True, "output_buffer": output})
    migration = _migration("0103_visit_consultation_completion.py")
    migration.op = Operations(ctx)
    with pytest.raises(RuntimeError, match="requires a live database preflight"):
        getattr(migration, direction)()
    assert output.getvalue() == ""

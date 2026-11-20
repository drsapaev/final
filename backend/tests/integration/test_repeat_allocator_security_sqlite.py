"""Synthetic SQLite checks for persisted repeat-evidence clocks."""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

FLOOR = 1 << 52


@pytest.fixture
def db():
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id integer PRIMARY KEY)"))
        conn.execute(sa.text("CREATE TABLE doctors (id integer PRIMARY KEY, user_id integer)"))
        conn.execute(sa.text("CREATE TABLE visits (id integer PRIMARY KEY, patient_id integer, doctor_id integer, visit_date date, status text)"))
        conn.execute(sa.text("CREATE TABLE visit_services (id integer PRIMARY KEY, visit_id integer, service_id integer, qty integer)"))
        conn.execute(sa.text("INSERT INTO doctors VALUES (1,NULL)"))
        conn.execute(sa.text("INSERT INTO visits VALUES (1,1,NULL,'2030-01-01','completed')"))
    with engine.connect() as conn:
        yield conn
    engine.dispose()


def _revision(conn, direction):
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0103_visit_consultation_completion.py"
    spec = importlib.util.spec_from_file_location("repeat_allocator_sqlite_0103", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.op = Operations(MigrationContext.configure(conn))
    getattr(module, direction)()


def test_rejects_existing_unconstrained_low_clock(db):
    db.execute(sa.text("CREATE TABLE repeat_evidence_generation_clock (id INTEGER PRIMARY KEY,value INTEGER NOT NULL)"))
    db.execute(sa.text("INSERT INTO repeat_evidence_generation_clock VALUES (1,1)"))
    with pytest.raises(RuntimeError, match="allocator clock schema"):
        _revision(db, "upgrade")


def test_persistent_clock_survives_downgrade_and_reupgrade(db):
    _revision(db, "upgrade")
    first = db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one()
    _revision(db, "downgrade")
    _revision(db, "upgrade")
    second = db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=1")).scalar_one()
    assert FLOOR < first < second


def test_evidence_invalidates_context_and_keeps_unchanged_service(db):
    _revision(db, "upgrade")
    db.execute(sa.text("INSERT INTO users VALUES (1),(2)"))
    db.execute(sa.text("UPDATE doctors SET user_id=1 WHERE id=1"))
    db.execute(sa.text("INSERT INTO visits VALUES (2,1,1,'2030-01-02','open',0,NULL,NULL,NULL,NULL,NULL)"))
    db.execute(sa.text("INSERT INTO visit_services VALUES (1,2,10,1)"))
    before = db.execute(sa.text("SELECT repeat_evidence_generation FROM visits WHERE id=2")).scalar_one()
    db.execute(sa.text("UPDATE visits SET status='completed',repeat_proof_generation=:g,repeat_proof_consultation=1,repeat_proof_doctor_user_id=1 WHERE id=2"), {"g": before})
    db.execute(sa.text("UPDATE visit_services SET qty=qty WHERE id=1"))
    assert db.execute(sa.text("SELECT repeat_evidence_generation,repeat_proof_generation FROM visits WHERE id=2")).one() == (before, before)
    db.execute(sa.text("UPDATE doctors SET user_id=2 WHERE id=1"))
    db.execute(sa.text("UPDATE doctors SET user_id=1 WHERE id=1"))
    assert db.execute(sa.text("SELECT repeat_proof_doctor_user_id FROM visits WHERE id=2")).scalar_one() == 1
    db.execute(sa.text("UPDATE visits SET visit_date='2030-01-03' WHERE id=2"))
    db.execute(sa.text("UPDATE visits SET visit_date='2030-01-02' WHERE id=2"))
    row = db.execute(sa.text("SELECT repeat_evidence_generation,repeat_proof_generation FROM visits WHERE id=2")).one()
    assert row[0] > before and row[1] is None


def test_doctor_reassignment_during_care_cannot_create_owner_provenance(db):
    _revision(db, "upgrade")
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


def test_direct_assignment_injection_and_restore_after_rebind_are_refused(db):
    _revision(db, "upgrade")
    db.execute(sa.text("INSERT INTO users VALUES (1),(2)"))
    db.execute(sa.text("UPDATE doctors SET user_id=1 WHERE id=1"))
    db.execute(sa.text("INSERT INTO visits (id,patient_id,doctor_id,visit_date,status) VALUES (2,1,1,'2030-01-02','in_progress'),(3,1,1,'2030-01-03','open')"))
    with pytest.raises(sa.exc.IntegrityError, match="invalid repeat assignment provenance"):
        db.execute(sa.text("UPDATE visits SET repeat_assigned_doctor_user_id=1, repeat_assigned_owner_generation=(SELECT repeat_owner_generation FROM doctors WHERE id=1) WHERE id=2"))
    db.execute(sa.text("UPDATE doctors SET user_id=2 WHERE id=1"))
    db.execute(sa.text("UPDATE doctors SET user_id=1 WHERE id=1"))
    assert db.execute(sa.text("SELECT repeat_assigned_doctor_user_id FROM visits WHERE id=3")).scalar_one() is None
    with pytest.raises(sa.exc.IntegrityError, match="invalid repeat assignment provenance"):
        db.execute(sa.text("UPDATE visits SET repeat_assigned_doctor_user_id=1, repeat_assigned_owner_generation=(SELECT repeat_owner_generation FROM doctors WHERE id=1) WHERE id=3"))


def test_rejects_missing_guard_on_retained_clock(db):
    _revision(db, "upgrade")
    _revision(db, "downgrade")
    db.execute(sa.text("DROP TRIGGER trg_repeat_clock_no_delete"))
    with pytest.raises(RuntimeError, match="allocator clock guards"):
        _revision(db, "upgrade")


def test_rejects_temporary_table_shadow(db):
    db.execute(sa.text("CREATE TEMP TABLE repeat_evidence_generation_clock (id INTEGER,value INTEGER)"))
    db.execute(sa.text("INSERT INTO temp.repeat_evidence_generation_clock VALUES (1,1)"))
    with pytest.raises(RuntimeError, match="temporary shadow"):
        _revision(db, "upgrade")


def test_downgrade_refuses_temp_visit_shadow(db):
    _revision(db, "upgrade")
    db.execute(sa.text("CREATE TEMP TABLE visits (id INTEGER)"))
    with pytest.raises(RuntimeError, match="temporary shadow"):
        _revision(db, "downgrade")
    assert db.execute(sa.text("SELECT repeat_evidence_generation FROM main.visits WHERE id=1")).scalar_one() > FLOOR


def test_downgrade_refuses_missing_persistent_clock(db):
    _revision(db, "upgrade")
    db.execute(sa.text("DROP TRIGGER trg_repeat_clock_no_delete"))
    db.execute(sa.text("DROP TABLE repeat_evidence_generation_clock"))
    with pytest.raises(RuntimeError, match="allocator clock is missing"):
        _revision(db, "downgrade")

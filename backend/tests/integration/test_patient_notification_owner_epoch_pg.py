"""PostgreSQL row-lock and ABA checks for the real 0110/0113 migrations."""

import os
import threading
from uuid import uuid4

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from tests.integration.test_patient_notification_owner_epoch_migration import (
    generation,
    migration,
)


@pytest.fixture
def pg_engine():
    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith(
        "clinic_test"
    ):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    schema = "test_patient_owner_epoch_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(
        url, connect_args={"options": f"-csearch_path={schema} -clock_timeout=10000"}
    )
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            conn.execute(
                text(
                    "CREATE TABLE patients (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL, is_deleted BOOLEAN NOT NULL DEFAULT FALSE, birth_date DATE)"
                )
            )
            conn.execute(text("INSERT INTO users VALUES (1),(2)"))
            conn.execute(text("INSERT INTO patients (id,user_id) VALUES (1,1)"))
            with Operations.context(MigrationContext.configure(conn)):
                migration("0110_patient_birth_precision.py").upgrade()
                migration("0113_subject_ownership.py").upgrade()
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_actual_triggers_aba_noop_rollback_and_delete(pg_engine):
    with pg_engine.connect() as conn:
        transaction = conn.begin()
        conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        assert generation(conn) == 2
        transaction.rollback()
        assert generation(conn) == 1
        conn.execute(
            text("UPDATE patients SET notification_owner_generation=999 WHERE id=1")
        )
        assert generation(conn) == 1
        conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        conn.execute(text("UPDATE patients SET user_id=1 WHERE id=1"))
        conn.execute(text("UPDATE patients SET is_deleted=TRUE WHERE id=1"))
        conn.execute(text("UPDATE patients SET is_deleted=FALSE WHERE id=1"))
        assert generation(conn) == 6
        conn.execute(text("DELETE FROM users WHERE id=1"))
        assert generation(conn) == 7
        assert (
            conn.execute(text("SELECT user_id FROM patients WHERE id=1")).scalar_one()
            is None
        )
        conn.commit()


def test_reader_waits_for_concurrent_rebind_then_sees_new_generation(pg_engine):
    ready = threading.Event()
    pid = []
    observed = []
    errors = []

    def reader():
        try:
            with pg_engine.connect() as conn:
                pid.append(conn.connection.driver_connection.info.backend_pid)
                ready.set()
                observed.append(
                    conn.execute(
                        text(
                            "SELECT user_id, notification_owner_generation FROM patients WHERE id=1 FOR UPDATE"
                        )
                    ).one()
                )
        except BaseException as exc:
            errors.append(exc)

    with pg_engine.connect() as writer:
        transaction = writer.begin()
        writer.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        assert ready.wait(5)
        with pg_engine.connect() as observer:
            # Wait until the server has registered the lock wait, not just
            # until the thread has acquired its connection.
            for _ in range(100):
                if observer.execute(
                    text("SELECT cardinality(pg_blocking_pids(:pid)) > 0"),
                    {"pid": pid[0]},
                ).scalar():
                    break
                threading.Event().wait(0.01)
            else:
                pytest.fail("reader did not wait for patient row lock")
        transaction.commit()
        thread.join(10)
    assert not thread.is_alive() and not errors
    assert tuple(observed[0]) == (2, 2)


def test_counter_overflow_rejects_owner_change(pg_engine):
    from sqlalchemy.exc import DBAPIError

    with pg_engine.begin() as conn:
        # Synthetic sequence exhaustion; real writers cannot restart the clock.
        conn.execute(
            text(
                "SELECT setval('patient_notification_owner_clock', 9223372036854775807, true)"
            )
        )
    with pg_engine.connect() as conn:
        with pytest.raises(DBAPIError):
            conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        conn.rollback()
        assert generation(conn) == 1


def test_deleted_patient_id_reuse_gets_new_epoch(pg_engine):
    with pg_engine.begin() as conn:
        old = generation(conn)
        conn.execute(text("DELETE FROM patients WHERE id=1"))
        conn.execute(text("INSERT INTO patients (id,user_id) VALUES (1,1)"))
        assert generation(conn) > old


def test_fully_migrated_pg_preserves_ownership_epoch_across_id_reuse():
    """Run only against an explicitly disposable database migrated through 0113."""
    from sqlalchemy.orm import Session

    from app.models.patient import Patient
    from app.models.user import User

    url = make_url(os.getenv("DATABASE_URL", "sqlite://"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith(
        "clinic_test"
    ):
        pytest.skip("requires disposable clinic_test PostgreSQL")
    engine = create_engine(url)
    try:
        with engine.connect() as conn:
            version = conn.execute(
                text("SELECT version_num FROM alembic_version")
            ).scalar_one_or_none()
            if version != "0113_subject_ownership":
                pytest.skip("requires migration chain through 0113")
            conn.rollback()
            outer = conn.begin()
            try:
                with Session(bind=conn, join_transaction_mode="create_savepoint") as db:
                    suffix = uuid4().hex
                    a = User(
                        username="synthetic-owner-a-" + suffix,
                        hashed_password="synthetic",
                        role="Patient",
                        is_active=True,
                    )
                    b = User(
                        username="synthetic-owner-b-" + suffix,
                        hashed_password="synthetic",
                        role="Patient",
                        is_active=True,
                    )
                    db.add_all([a, b])
                    db.flush()
                    patient = Patient(
                        first_name="Synthetic", last_name="Owner", user_id=a.id
                    )
                    db.add(patient)
                    db.flush()
                    first_id = patient.id
                    first_generation = patient.notification_owner_generation
                    patient.user_id = b.id
                    db.flush()
                    db.refresh(patient)
                    assert patient.notification_owner_generation > first_generation
                    patient.user_id = a.id
                    db.flush()
                    db.refresh(patient)
                    after_aba = patient.notification_owner_generation
                    assert after_aba > first_generation
                    db.delete(patient)
                    db.flush()
                    replacement = Patient(
                        id=first_id,
                        first_name="Synthetic",
                        last_name="Replacement",
                        user_id=a.id,
                    )
                    db.add(replacement)
                    db.flush()
                    assert replacement.notification_owner_generation > after_aba
                    db.commit()
            finally:
                outer.rollback()
    finally:
        engine.dispose()


def test_downgrade_reupgrade_cannot_revive_old_subject(pg_engine):
    with pg_engine.begin() as conn:
        old_subject = (1, generation(conn))
        conn.execute(text("DELETE FROM patients WHERE id=1"))
        with Operations.context(MigrationContext.configure(conn)):
            migration("0113_subject_ownership.py").downgrade()
        conn.execute(text("INSERT INTO patients (id,user_id) VALUES (1,1)"))
        with Operations.context(MigrationContext.configure(conn)):
            migration("0113_subject_ownership.py").upgrade()
        new_subject = (1, generation(conn))
        assert new_subject[1] > old_subject[1]
        assert new_subject != old_subject

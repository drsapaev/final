"""Actual 0110+0113 trigger behavior over a synthetic predecessor."""

import importlib.util
import io
import os
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.schema import CreateSchema, DropSchema

VERSIONS = Path(__file__).resolve().parents[2] / "alembic/versions"


def migration(filename):
    spec = importlib.util.spec_from_file_location(
        "test_" + filename.removesuffix(".py"), VERSIONS / filename
    )
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def predecessor(conn):
    conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
    conn.execute(
        text("""CREATE TABLE patients (
        id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL,
        is_deleted BOOLEAN NOT NULL DEFAULT 0, birth_date DATE
    )""")
    )
    conn.execute(text("INSERT INTO users (id) VALUES (1),(2)"))
    conn.execute(text("INSERT INTO patients (id,user_id) VALUES (1,1)"))
    with Operations.context(MigrationContext.configure(conn)):
        migration("0110_patient_birth_precision.py").upgrade()
        migration("0113_subject_ownership.py").upgrade()


@pytest.fixture
def sqlite_engine(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'subject.sqlite'}")

    @event.listens_for(engine, "connect")
    def fk_on(conn, record):
        conn.execute("PRAGMA foreign_keys=ON")

    with engine.begin() as conn:
        predecessor(conn)
    yield engine
    engine.dispose()


def generation(conn, patient_id=1):
    return conn.execute(
        text("SELECT notification_owner_generation FROM patients WHERE id=:id"),
        {"id": patient_id},
    ).scalar_one()


def test_aba_bulk_null_delete_soft_delete_and_noop(sqlite_engine):
    with sqlite_engine.begin() as conn:
        assert generation(conn) == 1
        conn.execute(
            text(
                "UPDATE patients SET user_id=user_id, is_deleted=is_deleted WHERE id=1"
            )
        )
        assert generation(conn) == 1
        conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        assert generation(conn) == 2
        conn.execute(text("UPDATE patients SET user_id=1 WHERE id=1"))
        assert generation(conn) == 3
        conn.execute(text("UPDATE patients SET is_deleted=1 WHERE id=1"))
        conn.execute(text("UPDATE patients SET is_deleted=0 WHERE id=1"))
        assert generation(conn) == 5
        conn.execute(text("DELETE FROM users WHERE id=1"))
        assert generation(conn) == 6
        assert (
            conn.execute(text("SELECT user_id FROM patients WHERE id=1")).scalar_one()
            is None
        )
        conn.execute(text("INSERT INTO patients (id,user_id) VALUES (2,2)"))
        assert generation(conn, 2) == 7
        # The actual 0110 trigger remains active alongside the new trigger.
        assert (
            conn.execute(
                text("SELECT birth_date_generation FROM patients WHERE id=1")
            ).scalar_one()
            >= 4
        )


def test_rollbacks_and_attempts_to_reduce_generation_fail(sqlite_engine):
    with sqlite_engine.connect() as conn:
        transaction = conn.begin()
        conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        assert generation(conn) == 2
        transaction.rollback()
        assert generation(conn) == 1
        with pytest.raises(IntegrityError):
            conn.execute(
                text("UPDATE patients SET notification_owner_generation=0 WHERE id=1")
            )
        conn.rollback()
        with pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO patients (id, notification_owner_generation) VALUES (2,123)"
                )
            )
        conn.rollback()
        with pytest.raises(IntegrityError):
            with Operations.context(MigrationContext.configure(conn)):
                migration("0113_subject_ownership.py").downgrade()
        conn.rollback()
        assert generation(conn) == 1


def test_offline_postgres_upgrade_and_downgrade_contain_guards():
    buffer = io.StringIO()
    context = MigrationContext.configure(
        url="postgresql://", opts={"as_sql": True, "output_buffer": buffer}
    )
    with Operations.context(context):
        module = migration("0113_subject_ownership.py")
        module.upgrade()
        module.downgrade()
    output = buffer.getvalue()
    assert "row_security = off" in output
    assert "OLD.user_id" in output
    assert "OLD.is_deleted" in output
    assert "requires an empty patient table" in output


def test_overflow_fails_closed_and_empty_database_can_downgrade(sqlite_engine):
    # Synthetic setup only: place the counter at its terminal value while
    # preserving the production guard before exercising the ownership write.
    with sqlite_engine.begin() as conn:
        ddl = conn.execute(
            text(
                "SELECT sql FROM sqlite_master WHERE name='trg_patient_notification_clock_update'"
            )
        ).scalar_one()
        conn.execute(text("DROP TRIGGER trg_patient_notification_clock_update"))
        conn.execute(
            text(
                "UPDATE patient_notification_owner_clock SET value=9223372036854775807 WHERE id=1"
            )
        )
        conn.execute(text(ddl))
    with sqlite_engine.connect() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        conn.rollback()
        assert generation(conn) == 1
        conn.execute(text("DELETE FROM patients"))
        with Operations.context(MigrationContext.configure(conn)):
            migration("0113_subject_ownership.py").downgrade()
        conn.commit()
        assert "notification_owner_generation" not in [
            row[1] for row in conn.execute(text("PRAGMA table_info(patients)"))
        ]


@pytest.mark.parametrize("recursive", [0, 1])
def test_clock_is_protected_and_patient_id_reuse_has_new_epoch(
    sqlite_engine, recursive
):
    with sqlite_engine.connect() as conn:
        conn.execute(text(f"PRAGMA recursive_triggers={recursive}"))
        old = generation(conn)
        conn.execute(text("DELETE FROM patients WHERE id=1"))
        conn.execute(text("INSERT INTO patients (id,user_id) VALUES (1,1)"))
        assert generation(conn) > old
        conn.commit()
        for sql in (
            "DELETE FROM patient_notification_owner_clock",
            "INSERT OR REPLACE INTO patient_notification_owner_clock (id,value) VALUES (1,0)",
            "UPDATE patient_notification_owner_clock SET value=0",
        ):
            with pytest.raises(IntegrityError):
                conn.execute(text(sql))
            conn.rollback()
        current = generation(conn)
        conn.execute(text("UPDATE patients SET user_id=2 WHERE id=1"))
        assert generation(conn) > current
        conn.commit()


def test_existing_patients_get_distinct_epochs_and_insert_returning_requires_refresh(
    tmp_path,
):
    engine = create_engine(f"sqlite:///{tmp_path / 'backfill.sqlite'}")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            conn.execute(
                text(
                    "CREATE TABLE patients (id INTEGER PRIMARY KEY, user_id INTEGER REFERENCES users(id), is_deleted BOOLEAN NOT NULL DEFAULT 0, birth_date DATE)"
                )
            )
            conn.execute(text("INSERT INTO patients (id) VALUES (7),(20),(30)"))
            with Operations.context(MigrationContext.configure(conn)):
                migration("0110_patient_birth_precision.py").upgrade()
                migration("0113_subject_ownership.py").upgrade()
            values = list(
                conn.execute(
                    text(
                        "SELECT notification_owner_generation FROM patients ORDER BY id"
                    )
                ).scalars()
            )
            assert values == [1, 2, 3]
            returning = conn.execute(
                text(
                    "INSERT INTO patients (id) VALUES (40) RETURNING notification_owner_generation"
                )
            ).scalar_one()
            assert returning == 0
            assert generation(conn, 40) == 4
    finally:
        engine.dispose()


@pytest.mark.parametrize("recursive", [0, 1])
def test_downgrade_reupgrade_cannot_revive_old_subject(sqlite_engine, recursive):
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"PRAGMA recursive_triggers={recursive}"))
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


@pytest.mark.integration
def test_postgres_subject_generation_ignores_nonowner_shadow_path():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires disposable PostgreSQL clinic_test database")
    suffix = uuid.uuid4().hex
    trusted, shadow, role = "owner_real_" + suffix, "owner_shadow_" + suffix, "owner_role_" + suffix
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(trusted))
        conn.execute(CreateSchema(shadow))
        conn.execute(text(f'CREATE ROLE "{role}" NOLOGIN'))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={trusted}"})
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE users (id INTEGER PRIMARY KEY)"))
            conn.execute(text("CREATE TABLE patients (id INTEGER PRIMARY KEY, user_id INTEGER UNIQUE REFERENCES users(id) ON DELETE SET NULL, is_deleted BOOLEAN NOT NULL DEFAULT FALSE, birth_date DATE)"))
            conn.execute(text("INSERT INTO users VALUES (1),(2)"))
            conn.execute(text("INSERT INTO patients(id,user_id) VALUES (1,1)"))
            with Operations.context(MigrationContext.configure(conn)):
                migration("0110_patient_birth_precision.py").upgrade()
                migration("0113_subject_ownership.py").upgrade()
            old = generation(conn)
            conn.execute(text(f'CREATE SEQUENCE "{shadow}".patient_notification_owner_clock'))
            conn.execute(text(f'CREATE FUNCTION "{shadow}".nextval(regclass) RETURNS bigint LANGUAGE sql AS $$ SELECT 1::bigint $$'))
            conn.execute(text(f'GRANT USAGE ON SCHEMA "{trusted}", "{shadow}" TO "{role}"'))
            conn.execute(text(f'GRANT SELECT, UPDATE ON "{trusted}".patients TO "{role}"'))
            conn.execute(text(f'GRANT USAGE ON SEQUENCE "{trusted}".patient_notification_owner_clock, "{trusted}".patient_birth_generation_seq TO "{role}"'))
            conn.execute(text(f'SET LOCAL ROLE "{role}"'))
            conn.execute(text(f'SET LOCAL search_path TO "{shadow}", "{trusted}", pg_catalog'))
            conn.execute(text(f'UPDATE "{trusted}".patients SET user_id=2 WHERE id=1'))
            first = conn.execute(text(f'SELECT notification_owner_generation FROM "{trusted}".patients WHERE id=1')).scalar_one()
            assert first > old
            conn.execute(text(f'UPDATE "{trusted}".patients SET user_id=1 WHERE id=1'))
            assert conn.execute(text(f'SELECT notification_owner_generation FROM "{trusted}".patients WHERE id=1')).scalar_one() > first
            conn.execute(text("RESET ROLE"))
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(shadow, cascade=True))
            conn.execute(DropSchema(trusted, cascade=True))
            conn.execute(text(f'DROP ROLE "{role}"'))
        admin.dispose()

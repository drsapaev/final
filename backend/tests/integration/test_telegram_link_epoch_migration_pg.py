"""Exercise the actual Alembic revision and database trigger on PostgreSQL."""

import importlib.util
import os
import uuid
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema


@pytest.mark.integration
def test_link_epoch_upgrade_bulk_revoke_rollback_and_downgrade():
    url = make_url(os.environ.get("DATABASE_URL", "sqlite:///:memory:"))
    if url.get_backend_name() != "postgresql" or not (url.database or "").startswith("clinic_test"):
        pytest.skip("requires explicitly disposable PostgreSQL clinic_test database")
    schema = "test_tg_epoch_" + uuid.uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0101_telegram_patient_link_epoch.py"
    spec = importlib.util.spec_from_file_location("test_link_epoch_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE telegram_users (id integer PRIMARY KEY, patient_id integer, chat_id bigint, active boolean, blocked boolean, notifications_enabled boolean, appointment_reminders boolean)"))
            conn.execute(text("INSERT INTO telegram_users VALUES (1, 7, 123, true, false, true, true)"))
            migration.op = Operations(MigrationContext.configure(conn))
            migration.upgrade()
            initial = conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one()
            assert 0 < initial <= 2**52
            conn.execute(text("UPDATE telegram_users SET active = false"))
            revoked = conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one()
            assert revoked != initial
            conn.execute(text("UPDATE telegram_users SET active = true"))
            restored = conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one()
            assert restored not in (initial, revoked)
            conn.execute(text("UPDATE telegram_users SET patient_link_epoch = 0"))
            assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one() == restored
            savepoint = conn.begin_nested()
            conn.execute(text("UPDATE telegram_users SET patient_id = NULL"))
            rolled_back = conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one()
            assert rolled_back != restored
            savepoint.rollback()
            assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one() == restored
            conn.execute(text("UPDATE telegram_users SET patient_id = NULL"))
            assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one() not in (rolled_back, restored)
            migration.downgrade()
            migration.upgrade()
            reissued = conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one()
            assert 0 < reissued <= 2**52 and reissued != initial
            conn.execute(text("UPDATE telegram_users SET appointment_reminders = false"))
            assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one() != reissued
            conn.execute(text("INSERT INTO telegram_users (id, patient_id, chat_id) VALUES (2, 8, 124)"))
            inserted = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id = 2")).scalar_one()
            assert 0 < inserted <= 2**52 and inserted != reissued
            conn.execute(text("DELETE FROM telegram_users WHERE id = 2"))
            conn.execute(text("INSERT INTO telegram_users (id, patient_id, chat_id, patient_link_epoch) VALUES (2, 8, 124, :old)"), {"old": inserted})
            replacement = conn.execute(text("SELECT patient_link_epoch FROM telegram_users WHERE id = 2")).scalar_one()
            assert replacement != inserted
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


def test_sqlite_migration_fences_explicit_reinsert():
    engine = create_engine("sqlite:///:memory:")
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0101_telegram_patient_link_epoch.py"
    spec = importlib.util.spec_from_file_location("test_sqlite_link_epoch_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as conn:
        conn.execute(text("CREATE TABLE telegram_users (id integer PRIMARY KEY, patient_id integer, chat_id bigint, active boolean, blocked boolean, notifications_enabled boolean, appointment_reminders boolean)"))
        migration.op = Operations(MigrationContext.configure(conn))
        migration.upgrade()
        conn.execute(text("INSERT INTO telegram_users (id, patient_id, chat_id, patient_link_epoch) VALUES (1, 7, 123, 1)"))
        first = conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one()
        assert first != 1
        conn.execute(text("UPDATE telegram_users SET active = false"))
        changed = conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one()
        assert changed != first
        conn.execute(text("DELETE FROM telegram_users"))
        conn.execute(text("INSERT INTO telegram_users (id, patient_id, chat_id, patient_link_epoch) VALUES (1, 7, 123, :old)"), {"old": first})
        assert conn.execute(text("SELECT patient_link_epoch FROM telegram_users")).scalar_one() != first
        migration.downgrade()
        migration.upgrade()

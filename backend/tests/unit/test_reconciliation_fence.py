"""SQLite verifies local mutex triggers, not PostgreSQL privilege semantics."""
import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def sqlite_migration():
    engine = create_engine("sqlite://")
    path = Path(__file__).resolve().parents[2] / "alembic/versions/0123_reconciliation_fence.py"
    spec = importlib.util.spec_from_file_location("reconciliation_sqlite_0123", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    with engine.begin() as db:
        db.execute(text("CREATE TABLE provider_reconciliation_events (id integer primary key, phase text)"))
        db.execute(text("CREATE TABLE click_callback_receipts (id integer primary key, phase text)"))
        migration.op = Operations(MigrationContext.configure(db))
        migration.upgrade()
    yield engine, migration
    engine.dispose()


def test_empty_downgrade_reupgrade(sqlite_migration):
    engine, migration = sqlite_migration
    with engine.begin() as db:
        migration.op = Operations(MigrationContext.configure(db))
        migration.downgrade()
        migration.upgrade()
        assert db.execute(text("SELECT id FROM provider_reconciliation_mutex")).scalar_one() == 1


def test_complete_receipt_and_event_prevent_downgrade(sqlite_migration):
    engine, migration = sqlite_migration
    with engine.begin() as db:
        db.execute(text("INSERT INTO click_callback_receipts VALUES (1, 'complete')"))
    with engine.connect() as db:
        migration.op = Operations(MigrationContext.configure(db))
        with pytest.raises(IntegrityError):
            migration.downgrade()
        db.rollback()
        assert db.execute(text("SELECT count(*) FROM click_callback_receipts")).scalar_one() == 1
        assert db.execute(text("SELECT id FROM provider_reconciliation_mutex")).scalar_one() == 1


def test_mutex_singleton_cannot_be_removed(sqlite_migration):
    engine, _ = sqlite_migration
    with engine.begin() as db:
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text("DELETE FROM provider_reconciliation_mutex"))
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text("INSERT INTO provider_reconciliation_mutex VALUES (2)"))

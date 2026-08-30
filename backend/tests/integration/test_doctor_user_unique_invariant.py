"""DB invariant tests: doctors.user_id is UNIQUE (1 User = 1 Doctor).

Business invariant (see migration 0048_doctors_user_id_unique):

    1 physical doctor = 1 User account + 1 Doctor profile
    (doctors.user_id UNIQUE; multiple NULLs allowed for historical rows)

Covers:
- ORM/model level: inserting a second Doctor row for the same user_id raises
  IntegrityError (SQLite test DB enforces the column-level UNIQUE that is
  declared on the model and, in production, added by migration 0048).
- Multiple userless Doctor rows (user_id NULL) remain legal.
- Migration pre-condition logic: _duplicate_user_ids() detects duplicates and
  upgrade() aborts with RuntimeError before touching anything.
"""
from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app.models.clinic import Doctor
from app.models.user import User


def _make_user(db_session, username: str) -> User:
    user = User(username=username, hashed_password="x", role="Doctor")
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


def test_two_doctors_cannot_share_one_user(db_session) -> None:
    """Duplicate Doctor.user_id insert must fail at the DB level."""
    user = _make_user(db_session, "uq_dup_user")

    db_session.add(Doctor(user_id=user.id, specialty="stomatology", active=True))
    db_session.commit()

    db_session.add(Doctor(user_id=user.id, specialty="cardiology", active=True))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_multiple_userless_doctors_are_allowed(db_session) -> None:
    """NULL user_id rows (historical data) must NOT violate the constraint."""
    db_session.add_all(
        [
            Doctor(user_id=None, specialty="stomatology", active=True),
            Doctor(user_id=None, specialty="stomatology", active=True),
            Doctor(user_id=None, specialty="cardiology", active=False),
        ]
    )
    db_session.commit()

    count = (
        db_session.query(Doctor).filter(Doctor.user_id.is_(None)).count()
    )
    assert count == 3


def _load_migration():
    path = (
        Path(__file__)
        .resolve()
        .parents[2]
        / "alembic"
        / "versions"
        / "0048_doctors_user_id_unique.py"
    )
    spec = importlib.util.spec_from_file_location("mig_0048", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _scratch_doctors_table(engine: sa.Engine) -> sa.Connection:
    """Doctors table WITHOUT the unique constraint, mimicking pre-0048 state."""
    con = engine.connect()
    con.execute(
        sa.text(
            """
            CREATE TABLE doctors (
                id INTEGER PRIMARY KEY,
                user_id INTEGER,
                specialty VARCHAR(100) NOT NULL,
                active BOOLEAN NOT NULL DEFAULT 1
            )
            """
        )
    )
    con.commit()
    return con


def _seed(con: sa.Connection, sql: str) -> None:
    con.execute(sa.text(sql))
    con.commit()


def test_migration_upgrade_aborts_on_duplicates_and_touches_nothing(tmp_path) -> None:
    """Real upgrade() call: with duplicate links present it must raise
    RuntimeError BEFORE emitting any DDL (constraint must not appear)."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'precheck.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (7, 'stomatology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (7, 'stomatology')")

        # Bind a real alembic Operations context to the scratch connection so
        # upgrade() executes for real (op.get_bind(), batch_alter_table, ...).
        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))

        with pytest.raises(RuntimeError, match="MIGRATION ABORTED"):
            module.upgrade()

        # Nothing was touched: duplicates still there, no constraint created.
        assert module._duplicate_user_ids(con) == [(7, 2)]
        names = {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }
        assert "uq_doctors_user_id" not in names
    finally:
        con.close()


def test_migration_upgrade_creates_constraint_on_clean_data(tmp_path) -> None:
    """Real upgrade() call on clean data: constraint created (postcondition)."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'clean.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (2, 'stomatology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'lab')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()

        names = {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }
        assert "uq_doctors_user_id" in names

        # And the constraint actually enforces uniqueness now.
        with pytest.raises(IntegrityError):
            _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'lab')")
        con.rollback()
    finally:
        con.close()


def test_migration_downgrade_drops_constraint(tmp_path) -> None:
    """Real upgrade() then downgrade(): constraint removed, data preserved."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'down.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'lab')")

        from alembic.migration import MigrationContext
        from alembic.operations import Operations

        module.op = Operations(MigrationContext.configure(con))
        module.upgrade()
        assert "uq_doctors_user_id" in {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }

        module.downgrade()
        assert "uq_doctors_user_id" not in {
            uq["name"] for uq in sa.inspect(con).get_unique_constraints("doctors")
        }
        # Data preserved by rollback.
        count = con.execute(sa.text("SELECT COUNT(*) FROM doctors")).scalar()
        assert count == 2
    finally:
        con.close()


def test_migration_precondition_passes_without_duplicates(tmp_path) -> None:
    """With clean data, _duplicate_user_ids() returns an empty list."""
    module = _load_migration()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'clean.db'}")
    con = _scratch_doctors_table(engine)
    try:
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (1, 'cardiology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (2, 'stomatology')")
        _seed(con, "INSERT INTO doctors (user_id, specialty) VALUES (NULL, 'lab')")

        assert module._duplicate_user_ids(con) == []
    finally:
        con.close()

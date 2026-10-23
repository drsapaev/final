from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy import CheckConstraint, Integer, create_engine, text

from app.models.appointment import Appointment


def test_duration_snapshot_is_nullable_integer_without_implicit_backfill() -> None:
    column = Appointment.__table__.c.duration_minutes_snapshot

    assert isinstance(column.type, Integer)
    assert column.nullable is True
    assert column.default is None
    assert column.server_default is None


def test_duration_snapshot_requires_positive_values_when_present() -> None:
    checks = {
        constraint.name: str(constraint.sqltext)
        for constraint in Appointment.__table__.constraints
        if isinstance(constraint, CheckConstraint)
    }

    assert checks["ck_appointments_duration_snapshot_positive"] == (
        "duration_minutes_snapshot IS NULL OR duration_minutes_snapshot > 0"
    )


def test_migration_downgrade_preserves_recorded_duration_snapshots() -> None:
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0083_appointment_duration_snapshot.py"
    )
    spec = importlib.util.spec_from_file_location(
        "appointment_duration_snapshot_migration", migration_path
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    engine = create_engine("sqlite://")
    try:
        with engine.begin() as connection:
            connection.execute(
                text(
                    "CREATE TABLE appointments ("
                    "id INTEGER PRIMARY KEY, "
                    "duration_minutes_snapshot INTEGER NULL, "
                    "CONSTRAINT ck_appointments_duration_snapshot_positive "
                    "CHECK (duration_minutes_snapshot IS NULL OR "
                    "duration_minutes_snapshot > 0))"
                )
            )
            connection.execute(
                text(
                    "INSERT INTO appointments "
                    "(id, duration_minutes_snapshot) VALUES (1, 20)"
                )
            )

            context = MigrationContext.configure(connection)
            with Operations.context(context):
                with pytest.raises(RuntimeError, match="Refusing to remove"):
                    migration.downgrade()
    finally:
        engine.dispose()

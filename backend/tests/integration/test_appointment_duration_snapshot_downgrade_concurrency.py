"""PostgreSQL regression for snapshots committed during a downgrade."""

from __future__ import annotations

import importlib.util
import os
import time
import uuid
from collections.abc import Iterator
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path

import psycopg
import pytest
from alembic.migration import MigrationContext
from alembic.operations import Operations
from psycopg import sql
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

BACKEND_DIR = Path(__file__).resolve().parents[2]
MIGRATION_PATH = (
    BACKEND_DIR / "alembic" / "versions" / "0083_appointment_duration_snapshot.py"
)


def _load_migration():
    spec = importlib.util.spec_from_file_location(
        "appointment_duration_snapshot_migration", MIGRATION_PATH
    )
    assert spec is not None and spec.loader is not None
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    return migration


def _admin_url() -> str | None:
    explicit = os.getenv("BOOKING_SNAPSHOT_TEST_PG_ADMIN_URL", "").strip()
    candidates = [explicit] if explicit else []

    # GitHub Actions provisions an isolated PostgreSQL service for this suite.
    # Outside CI, require an explicit disposable-cluster URL so this test never
    # derives an admin connection from the clinic's local application database.
    if not explicit and os.getenv("CI", "").lower() in {"1", "true", "yes"}:
        database_url = os.getenv("DATABASE_URL", "").strip()
        if database_url:
            parsed = make_url(database_url)
            if parsed.host in {"localhost", "127.0.0.1", "::1"}:
                candidates.append(
                    parsed.set(
                        drivername="postgresql", database="postgres"
                    ).render_as_string(hide_password=False)
                )

    for candidate in candidates:
        try:
            parsed = make_url(candidate)
        except Exception:  # noqa: BLE001 - invalid opt-in should skip safely
            continue
        if parsed.host not in {"localhost", "127.0.0.1", "::1"}:
            continue
        admin_url = parsed.set(drivername="postgresql", database="postgres")
        rendered = admin_url.render_as_string(hide_password=False)
        try:
            with psycopg.connect(rendered, connect_timeout=5) as connection:
                connection.execute("SELECT 1")
            return rendered
        except Exception:  # noqa: BLE001 - availability is reported as skip
            continue
    return None


def _drop_database(admin_url: str, database_name: str) -> None:
    with psycopg.connect(admin_url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(
                sql.Identifier(database_name)
            )
        )


@pytest.fixture
def postgres_snapshot_database() -> Iterator[tuple[str, str]]:
    admin_url = _admin_url()
    if admin_url is None:
        pytest.skip("disposable loopback PostgreSQL admin connection is unavailable")

    database_name = f"booking_snapshot_race_{uuid.uuid4().hex[:12]}"
    try:
        with psycopg.connect(admin_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
            )
    except Exception as exc:  # noqa: BLE001 - lack of CREATEDB is not a code failure
        pytest.skip(
            f"cannot create an isolated PostgreSQL database ({type(exc).__name__})"
        )

    database_url = (
        make_url(admin_url)
        .set(drivername="postgresql+psycopg", database=database_name)
        .render_as_string(hide_password=False)
    )
    engine = create_engine(database_url, poolclass=NullPool)
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
                    "(id, duration_minutes_snapshot) VALUES (1, NULL)"
                )
            )
        yield database_url, admin_url
    finally:
        engine.dispose()
        _drop_database(admin_url, database_name)


def _run_downgrade(database_url: str, pid_ready: Future[int]) -> str:
    migration = _load_migration()
    engine = create_engine(database_url, poolclass=NullPool)
    try:
        with engine.begin() as connection:
            pid_ready.set_result(
                connection.execute(text("SELECT pg_backend_pid()")).scalar_one()
            )
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                migration.downgrade()
        return "downgrade completed"
    except RuntimeError as exc:
        if "Refusing to remove appointment duration snapshots" not in str(exc):
            raise
        return "downgrade refused"
    finally:
        engine.dispose()


@pytest.mark.integration
def test_downgrade_waits_for_concurrent_snapshot_then_refuses_drop(
    postgres_snapshot_database: tuple[str, str],
) -> None:
    database_url, admin_url = postgres_snapshot_database
    writer_url = (
        make_url(database_url)
        .set(drivername="postgresql")
        .render_as_string(hide_password=False)
    )
    writer = psycopg.connect(writer_url, connect_timeout=5)
    executor = ThreadPoolExecutor(max_workers=1)
    pid_ready: Future[int] = Future()
    downgrade = None

    try:
        # Keep the new snapshot uncommitted while the downgrade reaches the
        # table lock. Without the guard lock, its SELECT can see NULL, then
        # DROP COLUMN waits here and deletes the snapshot after this commits.
        writer.execute(
            "UPDATE appointments SET duration_minutes_snapshot = 20 WHERE id = 1"
        )
        downgrade = executor.submit(_run_downgrade, database_url, pid_ready)
        migration_pid = pid_ready.result(timeout=5)

        waiting_for_lock = False
        deadline = time.monotonic() + 5
        with psycopg.connect(admin_url, autocommit=True) as observer:
            while time.monotonic() < deadline:
                row = observer.execute(
                    "SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s",
                    (migration_pid,),
                ).fetchone()
                if row is not None and row[0] == "Lock":
                    waiting_for_lock = True
                    break
                if downgrade.done():
                    break
                time.sleep(0.01)

        assert waiting_for_lock, "downgrade did not wait for the active writer"
        writer.commit()
        assert downgrade.result(timeout=10) == "downgrade refused"

        inspect_engine = create_engine(database_url, poolclass=NullPool)
        try:
            with inspect_engine.connect() as connection:
                columns = {
                    row.column_name
                    for row in connection.execute(
                        text(
                            "SELECT column_name FROM information_schema.columns "
                            "WHERE table_schema = current_schema() "
                            "AND table_name = 'appointments'"
                        )
                    )
                }
                snapshot = connection.execute(
                    text(
                        "SELECT duration_minutes_snapshot FROM appointments "
                        "WHERE id = 1"
                    )
                ).scalar_one()
        finally:
            inspect_engine.dispose()

        assert "duration_minutes_snapshot" in columns
        assert snapshot == 20
    finally:
        if not writer.closed:
            writer.rollback()
            writer.close()
        if downgrade is not None and not downgrade.done():
            try:
                downgrade.result(timeout=10)
            except Exception:  # noqa: BLE001 - preserve the original test failure
                pass
        executor.shutdown(wait=True)

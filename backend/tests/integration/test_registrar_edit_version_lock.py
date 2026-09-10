"""Real PostgreSQL proof: a version check holds its row until the edit ends."""

import os
import threading
import time
from datetime import UTC, date, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

from app.db.base_class import Base
from app.models.online_queue import DailyQueue, OnlineQueueEntry
from app.services.registrar_edit_delta_service import RegistrarEditDeltaService

pytestmark = pytest.mark.gate_d


@pytest.fixture
def version_engine():
    url = make_url(os.environ["DATABASE_URL"])
    if url.get_backend_name() != "postgresql":
        pytest.fail("Version serialization requires PostgreSQL")
    if not url.database or not url.database.startswith("clinic_test"):
        pytest.fail("Use an explicitly disposable clinic_test database")
    # A unique schema isolates the fixture from other suites in the test database.
    schema = "test_edit_version_" + uuid4().hex
    admin = create_engine(url)
    with admin.begin() as conn:
        conn.execute(CreateSchema(schema))
    engine = create_engine(url, connect_args={"options": f"-csearch_path={schema}"})
    try:
        Base.metadata.create_all(engine)
        yield engine
    finally:
        engine.dispose()
        with admin.begin() as conn:
            conn.execute(DropSchema(schema, cascade=True))
        admin.dispose()


@pytest.fixture
def entry_version(version_engine):
    with Session(version_engine) as session:
        queue = DailyQueue(day=date.today(), queue_tag="SYNTHETIC-version")
        session.add(queue)
        session.flush()
        entry = OnlineQueueEntry(
            queue_id=queue.id,
            number=1,
            source="desk",
            patient_name="SYNTHETIC-Version",
            updated_at=datetime(2026, 1, 1, 10, 0, 0, 123456, tzinfo=UTC),
        )
        session.add(entry)
        session.commit()
        return entry.id, entry.updated_at


def _wait_for_blocker(engine, pid, finished):
    """Observe the PostgreSQL lock, rather than assuming a sleep means blocking."""
    deadline = time.monotonic() + 5
    with engine.connect() as conn:
        while time.monotonic() < deadline:
            if conn.scalar(
                text("SELECT cardinality(pg_blocking_pids(:pid))"), {"pid": pid}
            ):
                return True
            if finished.wait(0.01):
                return False
    return False


def test_waiting_guard_reloads_version_after_other_editor_commits(
    version_engine, entry_version
):
    entry_id, original = entry_version
    ready, finished = threading.Event(), threading.Event()
    result = {}

    with Session(version_engine) as first:
        first.execute(text("SET LOCAL statement_timeout = '8s'"))
        entry = (
            first.query(OnlineQueueEntry).filter_by(id=entry_id).with_for_update().one()
        )
        entry.updated_at = original + timedelta(milliseconds=100)
        first.flush()

        def second_editor():
            try:
                with Session(version_engine) as second:
                    second.execute(text("SET LOCAL statement_timeout = '8s'"))
                    # A quote or prior read can have populated the identity map.
                    cached = second.get(OnlineQueueEntry, entry_id)
                    assert cached.updated_at == original
                    result["pid"] = second.scalar(text("SELECT pg_backend_pid()"))
                    ready.set()
                    try:
                        RegistrarEditDeltaService(
                            second
                        )._assert_entries_not_concurrently_modified(
                            {entry_id: original.isoformat()}
                        )
                    except ValueError as error:
                        result["conflict"] = str(error)
            except Exception as error:
                result["error"] = repr(error)
            finally:
                finished.set()

        worker = threading.Thread(target=second_editor, daemon=True)
        worker.start()
        try:
            assert ready.wait(5), result
            blocked = _wait_for_blocker(version_engine, result["pid"], finished)
            first.commit()
            assert finished.wait(5), result
            assert blocked, (
                "Version check returned before the concurrent edit committed"
            )
            assert "error" not in result, result
            assert "изменена другим пользователем" in result.get("conflict", ""), result
        finally:
            first.rollback()
            worker.join(timeout=10)


def test_accepted_guard_holds_version_until_transaction_ends(
    version_engine, entry_version
):
    entry_id, original = entry_version
    ready, finished = threading.Event(), threading.Event()
    result = {}
    with Session(version_engine) as editing:
        RegistrarEditDeltaService(editing)._assert_entries_not_concurrently_modified(
            {entry_id: original.isoformat()}
        )

        def concurrent_update():
            try:
                with Session(version_engine) as other:
                    other.execute(text("SET LOCAL statement_timeout = '8s'"))
                    result["pid"] = other.scalar(text("SELECT pg_backend_pid()"))
                    ready.set()
                    other.execute(
                        text(
                            "UPDATE queue_entries SET updated_at = :stamp WHERE id = :id"
                        ),
                        {
                            "stamp": original + timedelta(milliseconds=100),
                            "id": entry_id,
                        },
                    )
                    other.commit()
            except Exception as error:
                result["error"] = repr(error)
            finally:
                finished.set()

        worker = threading.Thread(target=concurrent_update, daemon=True)
        worker.start()
        try:
            assert ready.wait(5), result
            blocked = _wait_for_blocker(version_engine, result["pid"], finished)
            editing.commit()
            assert finished.wait(5), result
            assert blocked, (
                "Another writer modified the entry after its version was accepted"
            )
            assert "error" not in result, result
        finally:
            editing.rollback()
            worker.join(timeout=10)

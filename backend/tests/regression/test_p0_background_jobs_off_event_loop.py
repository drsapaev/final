"""Regression tests for the P0 origin freeze of 2026-08-28.

Incident (py-spy evidence): ``_run_lab_notifications_periodically`` awaited
``run_lab_notifications`` directly on the event loop. Its call tree performs
sync SQLAlchemy I/O against remote Supabase; a stalled TCP socket left
psycopg ``wait_select`` spinning on the event loop thread, so uvicorn served
no request at all (health, /docs, everything) for minutes at a time.
``ScheduledBackupService.backup_loop`` has the same anti-pattern one level
worse: it calls ``create_backup`` (``subprocess.run`` of pg_dump) inline.

Fix under test: both periodic jobs must run their work in worker threads
(``run_in_executor``), the event loop must stay responsive while the job is
stuck, and shutdown must wait (bounded) for in-flight jobs instead of
leaving detached background threads.

Run:
    pytest backend/tests/regression/test_p0_background_jobs_off_event_loop.py -v
"""

from __future__ import annotations

import asyncio
import threading
import time as time_module
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from app.main import (
    _background_tasks,
    _inflight_thread_jobs,
    _shutdown_background_tasks,
    _startup_tasks,
)
from app.services.scheduled_backup import ScheduledBackupService

_TICK_INTERVAL = 0.05
_TICK_WINDOW = 1.0
_MIN_TICKS = 8  # a loop blocked by the job would manage ~0-2


class _FakeSession:
    """Stand-in for a SQLAlchemy session: only created and closed."""

    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _count_ticks(seconds: float) -> int:
    """Synchronous tick counter; must be driven via to_thread by the caller."""
    ticks = 0
    deadline = time_module.monotonic() + seconds
    while time_module.monotonic() < deadline:
        time_module.sleep(_TICK_INTERVAL)
        ticks += 1
    return ticks


async def _wait_for_event(event: threading.Event, timeout: float = 10.0) -> None:
    deadline = time_module.monotonic() + timeout
    while not event.is_set():
        if time_module.monotonic() > deadline:
            pytest.fail("background job never reached its blocking section")
        await asyncio.sleep(0.05)


@pytest.mark.asyncio
async def test_lab_scheduler_runs_off_event_loop_and_keeps_it_responsive(
    monkeypatch,
) -> None:
    """The 5-minute lab job must execute in a worker thread: the event loop
    must keep servicing requests while the job's sync DB call is stuck."""
    import app.db.session as db_session_module
    import app.main as main_module
    import app.services.lab_notification_service as lab_module

    main_thread_id = threading.get_ident()
    started = threading.Event()
    release = threading.Event()
    seen_thread_ids: list[int] = []
    sessions: list[_FakeSession] = []

    async def fake_run_lab_notifications(db):
        seen_thread_ids.append(threading.get_ident())
        started.set()
        # Simulate the incident: sync DB I/O stalling in the worker thread.
        await asyncio.to_thread(release.wait, 15)
        return {"ready_results": {}, "critical_values": {}}

    monkeypatch.setattr(lab_module, "run_lab_notifications", fake_run_lab_notifications)
    # SessionLocal() must yield a closeable fake session.
    monkeypatch.setattr(
        db_session_module,
        "SessionLocal",
        lambda: sessions.append(_FakeSession()) or sessions[-1],
    )
    monkeypatch.setattr(main_module.settings, "AUTO_BACKUP_ENABLED", False)

    await _startup_tasks()
    try:
        assert _background_tasks, "lab scheduler task was not registered"
        task = next(iter(_background_tasks))
        assert not task.done()

        await _wait_for_event(started)
        assert seen_thread_ids, "job never executed"
        assert seen_thread_ids[0] != main_thread_id, (
            "lab job ran on the event loop thread"
        )

        # While the job is stuck in its worker thread the event loop must
        # keep ticking at full cadence (this is what /health needs).
        ticks = await asyncio.to_thread(_count_ticks, _TICK_WINDOW)
        assert ticks >= _MIN_TICKS, (
            f"event loop starved by lab job: {ticks} ticks "
            f"in {_TICK_WINDOW}s (expected >={_MIN_TICKS})"
        )
    finally:
        release.set()
        await _shutdown_background_tasks()

    assert all(t.done() for t in _background_tasks)
    assert not _background_tasks, "shutdown must unregister scheduler tasks"
    assert sessions and sessions[0].closed, "worker thread must close its session"
    # Let done-callbacks (inflight discard) settle before asserting.
    await asyncio.sleep(0)
    assert not _inflight_thread_jobs, "no lab job may outlive shutdown"


@pytest.mark.asyncio
async def test_scheduled_backup_runs_off_event_loop_and_stop_waits_for_inflight(
    tmp_path: Path,
) -> None:
    """The scheduled backup (pg_dump via subprocess.run) must run in a worker
    thread, and stop() must wait for an in-flight dump instead of abandoning
    it as detached background work."""
    main_thread_id = threading.get_ident()
    started = threading.Event()
    release = threading.Event()
    seen_thread_ids: list[int] = []
    completed: list[str] = []

    class FakeBackupService:
        def create_backup(self, backup_type: str) -> dict:
            seen_thread_ids.append(threading.get_ident())
            started.set()
            release.wait(timeout=15)  # simulate a long pg_dump
            completed.append(backup_type)
            return {"filename": f"backup_{backup_type}_fake.db"}

    service = ScheduledBackupService(db=_FakeSession(), backup_dir=str(tmp_path))
    service.backup_service = FakeBackupService()

    run_at = (datetime.now() + timedelta(seconds=1)).time()
    await service.start_daily_backups(run_at)
    try:
        assert service.task is not None and not service.task.done()

        await _wait_for_event(started)
        assert seen_thread_ids, "backup job never executed"
        assert seen_thread_ids[0] != main_thread_id, (
            "pg_dump ran on the event loop thread"
        )

        ticks = await asyncio.to_thread(_count_ticks, _TICK_WINDOW)
        assert ticks >= _MIN_TICKS, (
            f"event loop starved by backup job: {ticks} ticks "
            f"in {_TICK_WINDOW}s (expected >={_MIN_TICKS})"
        )

        # Controlled shutdown: stop() must return only after the in-flight
        # dump thread finished.
        asyncio.get_running_loop().call_later(0.6, release.set)
        stop_started = time_module.monotonic()
        await service.stop()
        elapsed = time_module.monotonic() - stop_started
        assert elapsed >= 0.3, (
            f"stop() returned in {elapsed:.2f}s without waiting for the "
            "in-flight backup thread"
        )
        assert completed == ["scheduled"], "in-flight backup was abandoned"
    finally:
        release.set()

    assert service.task.done()
    assert not service._inflight, "in-flight job tracking leaked"


@pytest.mark.asyncio
async def test_backup_stop_cancels_idle_scheduler_immediately(
    tmp_path: Path,
) -> None:
    """With no backup running, stop() must cancel the sleeping scheduler
    task promptly and leave no tracked jobs behind."""
    service = ScheduledBackupService(db=_FakeSession(), backup_dir=str(tmp_path))
    service.backup_service = _NeverBackupService()

    tomorrow_2am = (datetime.now() + timedelta(days=1)).time()
    await service.start_daily_backups(tomorrow_2am)
    assert service.task is not None and not service.task.done()

    await service.stop()

    assert service.task.done()
    assert not service._inflight
    assert not service.running


class _NeverBackupService:
    def create_backup(self, backup_type: str) -> dict:  # pragma: no cover
        raise AssertionError("backup must not fire in this test")


@pytest.mark.asyncio
async def test_shutdown_grace_is_actually_bounded_and_job_thread_is_daemon(
    monkeypatch,
) -> None:
    """Codex follow-up on #2874: a stalled job must not block shutdown past
    the grace period, and its worker thread must be a daemon so the process
    can exit without joining it."""
    import app.db.session as db_session_module
    import app.main as main_module
    import app.services.lab_notification_service as lab_module

    started = threading.Event()
    release = threading.Event()
    seen_thread_ids: list[int] = []

    async def fake_run_lab_notifications(db):
        seen_thread_ids.append(threading.get_ident())
        started.set()
        # Block the daemon thread itself (no executor): simulates a stalled
        # sync DB call that will never finish within the grace period.
        release.wait(120)
        return {}

    monkeypatch.setattr(
        lab_module, "run_lab_notifications", fake_run_lab_notifications
    )
    monkeypatch.setattr(
        db_session_module,
        "SessionLocal",
        lambda: _FakeSession(),
    )
    monkeypatch.setattr(main_module.settings, "AUTO_BACKUP_ENABLED", False)
    # Shrink the grace so the test proves bounding instead of waiting 30s.
    monkeypatch.setattr(main_module, "_BACKGROUND_SHUTDOWN_GRACE_SECONDS", 1)

    await _startup_tasks()
    await _wait_for_event(started)

    worker = next(
        t for t in threading.enumerate() if t.ident == seen_thread_ids[0]
    )
    assert worker.daemon, "background job thread must be daemon"

    shutdown_started = time_module.monotonic()
    await _shutdown_background_tasks()
    elapsed = time_module.monotonic() - shutdown_started

    assert elapsed < 5, (
        f"shutdown blocked {elapsed:.1f}s past the 1s grace period — "
        "the grace is not actually bounded"
    )
    release.set()

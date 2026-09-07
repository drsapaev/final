"""PR-1 reminder pipeline wiring tests.

Proves the end-to-end reminder path contract:

    producer (scheduler) -> arq queue (ARQ_QUEUE_NAME) -> worker job
    (send_visit_reminder) -> NotificationSenderService
    .send_confirmation_reminder(db, visit_id, hours_before) ->
    visits.reminder_sent_at idempotency.

The live Redis -> real arq Worker proof runs only when ARQ_TEST_REDIS_URL /
REDIS_URL is configured (same gating as scripts/arq_enqueue_process_check.py,
#3091). The real Telegram network send stays a staging/manual proof by
design — CI must not depend on a real bot token.
"""

from __future__ import annotations

import os
import random
from datetime import UTC, datetime

import pytest

from app.core.config import settings


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeVisit:
    def __init__(self, id: int = 42, reminder_sent_at: datetime | None = None) -> None:
        self.id = id
        self.reminder_sent_at = reminder_sent_at


class _FakeQuery:
    def __init__(self, visit: FakeVisit) -> None:
        self._visit = visit

    def filter(self, *args, **kwargs):  # noqa: ANN002, ANN003
        return self

    def first(self) -> FakeVisit:
        return self._visit


class FakeDB:
    def __init__(self, visit: FakeVisit | None = None) -> None:
        self.visit = visit
        self.commits = 0
        self.rollbacks = 0

    def query(self, model):  # noqa: ANN001, ANN201
        return _FakeQuery(self.visit)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


class RecordingService:
    """Stands in for NotificationSenderService; records the exact call args."""

    calls: list[tuple[object, int, int]] = []
    next_result: dict = {"success": True, "channel": "telegram"}

    def __init__(self, db) -> None:  # noqa: ANN001
        self.db = db

    async def send_confirmation_reminder(
        self, db, visit_id: int, hours_before: int = 24
    ) -> dict:  # noqa: ANN001
        RecordingService.calls.append((db, visit_id, hours_before))
        return RecordingService.next_result


@pytest.fixture(autouse=True)
def _reset_recorder():
    RecordingService.calls = []
    RecordingService.next_result = {"success": True, "channel": "telegram"}
    yield
    RecordingService.calls = []


# ---------------------------------------------------------------------------
# Worker core: contract + idempotency (no DB, no Redis needed)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_reminder_calls_service_by_real_contract():
    """Worker must call send_confirmation_reminder(db, visit_id, hours_before=24)
    — the notifications_pkg/_reminders.py signature — and persist the marker."""
    from app.tasks.worker import _run_visit_reminder

    db = FakeDB(FakeVisit(id=42, reminder_sent_at=None))
    await _run_visit_reminder(db, visit_id=42, service_factory=RecordingService)

    assert RecordingService.calls == [(db, 42, 24)]
    assert db.visit.reminder_sent_at is not None
    assert db.commits == 1
    assert db.rollbacks == 0


@pytest.mark.asyncio
async def test_reminder_skips_when_already_sent():
    """Duplicate job / arq retry: reminder_sent_at set -> service not called."""
    from app.tasks.worker import _run_visit_reminder

    db = FakeDB(FakeVisit(id=42, reminder_sent_at=datetime(2026, 1, 1, tzinfo=UTC)))
    await _run_visit_reminder(db, visit_id=42, service_factory=RecordingService)

    assert RecordingService.calls == []
    assert db.commits == 0


@pytest.mark.asyncio
async def test_reminder_failure_keeps_marker_unset_for_retry():
    """Send failure -> RuntimeError for arq retry_policy, marker stays unset."""
    from app.tasks.worker import _run_visit_reminder

    RecordingService.next_result = {"success": False, "error": "boom"}
    db = FakeDB(FakeVisit(id=42, reminder_sent_at=None))

    with pytest.raises(RuntimeError, match="boom"):
        await _run_visit_reminder(db, visit_id=42, service_factory=RecordingService)

    assert db.visit.reminder_sent_at is None
    assert db.commits == 0
    assert db.rollbacks == 1


@pytest.mark.asyncio
async def test_reminder_missing_visit_is_a_clean_noop():
    from app.tasks.worker import _run_visit_reminder

    db = FakeDB(visit=None)
    await _run_visit_reminder(db, visit_id=999, service_factory=RecordingService)

    assert RecordingService.calls == []
    assert db.commits == 0


# ---------------------------------------------------------------------------
# Queue SSOT: producer targets the same queue the worker consumes
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_enqueue_targets_worker_queue(monkeypatch):
    """The producer must pass _queue_name=ARQ_QUEUE_NAME (the queue
    WorkerSettings consumes) — the historical default-queue enqueue stranded
    every business job on `arq:queue`."""
    import arq

    import app.tasks.scheduler as scheduler
    from app.tasks.worker import ARQ_QUEUE_NAME

    captured: dict = {}

    class FakePool:
        async def enqueue_job(self, func_name, *args, **kwargs):  # noqa: ANN002, ANN003
            captured["func"] = func_name
            captured["kwargs"] = kwargs
            return object()  # truthy job handle

        async def close(self) -> None:
            captured["closed"] = True

    async def fake_create_pool(redis_settings):  # noqa: ANN001
        return FakePool()

    monkeypatch.setattr(arq, "create_pool", fake_create_pool)

    job_id = await scheduler.enqueue_reminder(visit_id=7)

    assert captured["func"] == "send_visit_reminder"
    assert captured["kwargs"]["_queue_name"] == ARQ_QUEUE_NAME == "clinic"
    assert captured["kwargs"]["visit_id"] == 7
    assert captured["kwargs"]["_job_id"] == "reminder:visit:7:telegram"
    assert captured["closed"] is True
    assert job_id == "reminder:visit:7:telegram"


def test_worker_settings_consume_the_ssot_queue():
    from app.tasks.worker import ARQ_QUEUE_NAME, WorkerSettings

    assert ARQ_QUEUE_NAME == "clinic"
    assert WorkerSettings.queue_name == ARQ_QUEUE_NAME


# ---------------------------------------------------------------------------
# Fail-loud enqueue: a Redis outage must not look like a fake success
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_redis_failure_fails_loud_by_default(monkeypatch):
    import arq

    import app.tasks.scheduler as scheduler

    monkeypatch.setattr(settings, "ARQ_ENQUEUE_FAIL_LOUD", True)

    async def boom(redis_settings):  # noqa: ANN001
        raise ConnectionError("redis down")

    monkeypatch.setattr(arq, "create_pool", boom)

    with pytest.raises(scheduler.TaskEnqueueError, match="redis down"):
        await scheduler._enqueue("send_visit_reminder", visit_id=1)


@pytest.mark.asyncio
async def test_scheduler_redis_failure_can_stay_quiet_for_dev(monkeypatch):
    import arq

    import app.tasks.scheduler as scheduler

    monkeypatch.setattr(settings, "ARQ_ENQUEUE_FAIL_LOUD", False)

    async def boom(redis_settings):  # noqa: ANN001
        raise ConnectionError("redis down")

    monkeypatch.setattr(arq, "create_pool", boom)

    job_id = await scheduler._enqueue("send_visit_reminder", visit_id=1)
    assert job_id  # returned for dev convenience — but never a fake raise-free lie in prod


# ---------------------------------------------------------------------------
# Live business wiring (needs a real Redis; real Telegram send NOT required)
# ---------------------------------------------------------------------------

LIVE_REDIS_URL = (
    (os.getenv("ARQ_TEST_REDIS_URL") or os.getenv("REDIS_URL") or "").strip()
)


@pytest.mark.skipif(not LIVE_REDIS_URL, reason="ARQ_TEST_REDIS_URL/REDIS_URL not configured")
@pytest.mark.asyncio
async def test_live_business_wiring_enqueue_worker_service_idempotency(monkeypatch):
    """Real enqueue of the REAL `send_visit_reminder` job onto the REAL
    'clinic' queue of the TEST redis -> real arq Worker picks it up ->
    NotificationSenderService called with the right args -> a duplicate job
    never sends a second time (reminder_sent_at marker)."""
    from arq.connections import RedisSettings, create_pool
    from arq.worker import Worker

    import app.services.notification_service as notif_module
    import app.tasks.worker as worker_mod
    from app.tasks.scheduler import enqueue_reminder
    from app.tasks.worker import ARQ_QUEUE_NAME, WorkerSettings

    visit_id = random.randint(10**6, 10**9)  # unique per run -> unique job id
    shared_visit = FakeVisit(id=visit_id, reminder_sent_at=None)

    def fake_build_db_session():
        # Same Visit row on every job run, like the real DB would serve.
        class _FakeEngine:
            def dispose(self) -> None:
                pass

        return FakeDB(shared_visit), _FakeEngine()

    monkeypatch.setattr(worker_mod, "_build_db_session", fake_build_db_session)

    class RecordedLiveService:
        def __init__(self, db) -> None:  # noqa: ANN001
            self.db = db

        async def send_confirmation_reminder(self, db, vid, hours_before=24):  # noqa: ANN001
            RecordingService.calls.append((vid, hours_before))
            return {"success": True, "channel": "telegram"}

    monkeypatch.setattr(notif_module, "NotificationService", RecordedLiveService)
    monkeypatch.setattr(settings, "ARQ_REDIS_URL", LIVE_REDIS_URL)

    async def run_burst_worker(pool):
        worker = Worker(
            functions=WorkerSettings.functions,
            redis_pool=pool,
            queue_name=ARQ_QUEUE_NAME,
            burst=True,
            poll_delay=0.1,
            job_timeout=10,
            keep_result=60,
            handle_signals=False,
            max_jobs=2,
            log_results=False,
        )
        await worker.async_run()

    pool = await create_pool(RedisSettings.from_dsn(LIVE_REDIS_URL))
    try:
        job_id = await enqueue_reminder(visit_id=visit_id)
        assert job_id == f"reminder:visit:{visit_id}:telegram"

        await run_burst_worker(pool)

        assert RecordingService.calls == [(visit_id, 24)]
        assert shared_visit.reminder_sent_at is not None

        # Duplicate job (same idempotency key). Whether arq dedups by job id
        # (enqueue returns None) or re-runs the job after result expiry, the
        # reminder_sent_at marker must prevent a second notification.
        dup = await enqueue_reminder(visit_id=visit_id)
        await run_burst_worker(pool)

        assert len(RecordingService.calls) == 1  # exactly one notification, ever
    finally:
        await pool.delete(
            f"arq:queue:{ARQ_QUEUE_NAME}",
            f"arq:queue:{ARQ_QUEUE_NAME}:health-check",
            f"arq:queue:{ARQ_QUEUE_NAME}:stats",
            job_id,
        )
        await pool.aclose()

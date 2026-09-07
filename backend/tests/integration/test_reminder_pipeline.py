"""Reminder pipeline business wiring tests (PR-1).

Covers the end-to-end path the PR fixes:
    enqueue_reminder → arq 'clinic' queue → worker send_visit_reminder
    → NotificationSenderService.send_confirmation_reminder(db, visit_id,
    hours_before=24) → visits.reminder_sent_at (ORM + migration 0060).

Layers proved here:

1. Producer/worker queue SSOT (no Redis needed): the scheduler enqueues
   onto the same named queue the worker consumes — the old code silently
   fell back to arq's default 'arq:queue' while the worker listened on
   'clinic', stranding every job.
2. Fail-closed transport (no Redis needed): a Redis failure raises
   TaskEnqueueError instead of returning a phantom job ID that reads as
   "job successfully enqueued" (the old fail-open contract).
3. Worker contract + DB idempotency (no Redis needed): the job function
   calls the real service by its actual signature
   (db, visit_id, hours_before=24) — the old call passed (visit,
   hours_before=24), a guaranteed TypeError — and stamps the REAL ORM
   column visits.reminder_sent_at (migration 0060) so repeat runs never
   resend.
4. Full business wiring via a REAL Redis queue (marked ``redis``, skipped
   when no Redis is reachable — CI provides a redis service container):
   real enqueue → in-process burst worker picks the job up → service
   called once → reminder_sent_at stamped → a second forced delivery
   (fresh job ID, bypassing queue dedupe) does NOT resend.
"""

from __future__ import annotations

import asyncio
import socket
import sys
import uuid
from datetime import date
from urllib.parse import urlparse

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings

REDIS_URL = "redis://localhost:6379/0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakePool:
    """Minimal arq pool stand-in capturing enqueue_job calls."""

    def __init__(self, job="job-ok", exc: Exception | None = None):
        self._job = job
        self._exc = exc
        self.calls: list[tuple[str, tuple, dict]] = []
        self.closed = False

    async def enqueue_job(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
        if self._exc is not None:
            raise self._exc
        return self._job

    async def aclose(self):
        self.closed = True


def _redis_reachable(url: str = REDIS_URL) -> bool:
    parsed = urlparse(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 6379
    try:
        with socket.create_connection((host, port), timeout=1.0):
            return True
    except OSError:
        return False


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def pipeline_db(test_db, monkeypatch: pytest.MonkeyPatch):
    """Point the app settings at the session-scoped sqlite file DB so the
    worker's own ``create_engine(settings.DATABASE_URL)`` path opens the
    SAME database the test fixtures write to (test_db is file-based, not
    in-memory, precisely so cross-connection visibility works)."""
    monkeypatch.setattr(settings, "DATABASE_URL", str(test_db.url))
    return test_db


@pytest.fixture
def make_visit(pipeline_db):
    """Create a committed Patient+Doctor(User)+Visit row set on the test DB.

    Uses a plain sessionmaker (no savepoint wrapper) so the data is visible
    to the worker's own engine/connection — exactly like production, where
    the producer's transaction has long since committed when the worker runs.

    Rows are DELETED on teardown: the suite shares one session-scoped
    sqlite file DB, and leftover rows (4 visits/users per run) break the
    row-count assertions of unrelated tests that run later alphabetically
    (setup/slot-reservation/specialized-panels analytics).
    """
    from app.models.clinic import Doctor
    from app.models.patient import Patient
    from app.models.user import User
    from app.models.visit import Visit

    created: list[tuple[int, int, int, int]] = []

    def _make() -> int:
        suffix = uuid.uuid4().hex[:8]
        s = sessionmaker(bind=pipeline_db)()
        try:
            user = User(
                username=f"rempipe_{suffix}",
                email=f"rempipe_{suffix}@test.invalid",
                full_name="Reminder Pipeline Doctor",
                hashed_password="test-not-a-login-hash",
                role="Doctor",
                is_active=True,
                is_superuser=False,
            )
            s.add(user)
            s.flush()
            doctor = Doctor(user_id=user.id, specialty="Кардиология", active=True)
            s.add(doctor)
            s.flush()
            patient = Patient(
                first_name="Пайплайн",
                last_name=f"Тест_{suffix}",
                middle_name="Тестович",
                phone=f"+99890{int(uuid.uuid4().int % 10**7):07d}",
                birth_date=date(1990, 1, 1),
                address="Тестовый адрес",
            )
            s.add(patient)
            s.flush()
            visit = Visit(
                patient_id=patient.id,
                doctor_id=doctor.id,
                visit_date=date.today(),
                visit_time="10:00",
                status="pending_confirmation",
                discount_mode="none",
                department="cardiology",
                confirmation_token=f"rempipe-{suffix}",
                confirmation_channel="telegram",
            )
            s.add(visit)
            s.commit()
            created.append((visit.id, patient.id, doctor.id, user.id))
            return visit.id
        finally:
            s.close()

    yield _make

    # Teardown: bulk deletes in FK-safe order (no cascade-dependent rows
    # exist — these visits have no services/invoices attached).
    s = sessionmaker(bind=pipeline_db)()
    try:
        for visit_id, patient_id, doctor_id, user_id in created:
            s.query(Visit).filter(Visit.id == visit_id).delete()
            s.query(Patient).filter(Patient.id == patient_id).delete()
            s.query(Doctor).filter(Doctor.id == doctor_id).delete()
            s.query(User).filter(User.id == user_id).delete()
        s.commit()
    finally:
        s.close()


@pytest.fixture
def reminder_spy(monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    """Replace NotificationSenderService.send_confirmation_reminder with a
    recording stub — proves the CONTRACT the worker calls with, without any
    real Telegram/SMS/email dispatch. The real network send is exercised
    manually/staging by design (no bot token in CI)."""
    from app.services.notifications_pkg._reminders import RemindersMixin

    calls: list[dict] = []

    async def _spy(self, db, visit_id, hours_before=24):
        calls.append({"db": db, "visit_id": visit_id, "hours_before": hours_before})
        return {"success": True, "channel": "telegram"}

    monkeypatch.setattr(RemindersMixin, "send_confirmation_reminder", _spy)
    return calls


# ---------------------------------------------------------------------------
# 1. Queue SSOT (criterion 1)
# ---------------------------------------------------------------------------


def test_queue_ssot_worker_and_scheduler_use_same_queue():
    """Worker consumes and producer enqueues onto the SAME named queue."""
    from app.tasks.worker import QUEUE_NAME, WorkerSettings

    assert QUEUE_NAME == "clinic"
    assert WorkerSettings.queue_name == QUEUE_NAME


# ---------------------------------------------------------------------------
# 2. Producer contract + fail-closed transport (criteria 1 + 4)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_enqueue_reminder_targets_clinic_queue_with_deterministic_job_id(
    monkeypatch: pytest.MonkeyPatch,
):
    """Producer must enqueue send_visit_reminder onto 'clinic' explicitly."""
    from app.tasks import enqueue_reminder

    pool = _FakePool()

    async def _fake_create_pool(redis_settings):
        return pool

    import arq

    monkeypatch.setattr(arq, "create_pool", _fake_create_pool)

    job_id = await enqueue_reminder(visit_id=42)

    assert job_id == "reminder:visit:42:telegram"
    func, args, kwargs = pool.calls[0]
    assert func == "send_visit_reminder"
    assert args == ()
    assert kwargs["visit_id"] == 42
    assert kwargs["channel"] == "telegram"
    assert kwargs["_job_id"] == "reminder:visit:42:telegram"
    # THE fix: no _queue_name meant arq's default 'arq:queue' — a queue the
    # worker never listens on.
    assert kwargs["_queue_name"] == "clinic"
    assert pool.closed  # no pool leak on the happy path


@pytest.mark.asyncio
async def test_enqueue_duplicate_job_id_returns_id_honestly(
    monkeypatch: pytest.MonkeyPatch,
):
    """job is None (duplicate) means the job IS on the queue — returning the
    ID stays honest; no raise, no fake state."""
    from app.tasks import enqueue_reminder

    pool = _FakePool(job=None)  # arq returns None on duplicate job ID

    async def _fake_create_pool(redis_settings):
        return pool

    import arq

    monkeypatch.setattr(arq, "create_pool", _fake_create_pool)

    job_id = await enqueue_reminder(visit_id=7)
    assert job_id == "reminder:visit:7:telegram"


@pytest.mark.asyncio
async def test_enqueue_redis_failure_raises_instead_of_fake_success(
    monkeypatch: pytest.MonkeyPatch,
):
    """Criterion 4: Redis unreachable must NOT yield a phantom job ID."""
    from app.tasks import enqueue_reminder
    from app.tasks.scheduler import TaskEnqueueError

    pool = _FakePool(exc=ConnectionError("redis down"))

    async def _fake_create_pool(redis_settings):
        return pool

    import arq

    monkeypatch.setattr(arq, "create_pool", _fake_create_pool)

    with pytest.raises(TaskEnqueueError, match="send_visit_reminder"):
        await enqueue_reminder(visit_id=1)


@pytest.mark.asyncio
async def test_enqueue_missing_arq_raises_instead_of_fake_success(
    monkeypatch: pytest.MonkeyPatch,
):
    """Criterion 4: missing arq (ImportError) must fail loud, not log a
    warning and return a job ID nothing will ever process."""
    from app.tasks import enqueue_reminder
    from app.tasks.scheduler import TaskEnqueueError

    monkeypatch.setitem(sys.modules, "arq", None)  # forces ImportError

    with pytest.raises(TaskEnqueueError):
        await enqueue_reminder(visit_id=1)


# ---------------------------------------------------------------------------
# 3. Worker contract + DB idempotency (criteria 2 + 3 + retry semantics)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_worker_calls_service_by_real_contract_and_stamps_reminder_sent_at(
    pipeline_db, make_visit, reminder_spy
):
    """Criterion 2: the worker must call send_confirmation_reminder by its
    real signature (db, visit_id, hours_before=24) — the old code passed
    (visit, hours_before=24), binding visit into the db slot (TypeError).
    Criterion 3: success stamps the REAL ORM column visits.reminder_sent_at
    (migration 0060) — no raw SQL."""
    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()
    await send_visit_reminder({}, visit_id=visit_id, channel="telegram")

    assert len(reminder_spy) == 1
    call = reminder_spy[0]
    assert call["visit_id"] == visit_id
    assert call["hours_before"] == 24
    assert isinstance(call["db"], Session)  # a real DB session, not the visit

    fresh = sessionmaker(bind=pipeline_db)()
    try:
        visit = fresh.query(Visit).filter(Visit.id == visit_id).first()
        assert visit is not None
        assert visit.reminder_sent_at is not None
    finally:
        fresh.close()


@pytest.mark.asyncio
async def test_worker_send_failure_does_not_stamp_and_raises(
    pipeline_db, make_visit, monkeypatch: pytest.MonkeyPatch
):
    """Failure must leave reminder_sent_at NULL and raise so arq retries."""
    from app.models.visit import Visit
    from app.services.notifications_pkg._reminders import RemindersMixin
    from app.tasks.worker import send_visit_reminder

    async def _failing(self, db, visit_id, hours_before=24):
        return {"success": False, "error": "telegram unavailable"}

    monkeypatch.setattr(RemindersMixin, "send_confirmation_reminder", _failing)

    visit_id = make_visit()
    with pytest.raises(RuntimeError, match="Notification send failed"):
        await send_visit_reminder({}, visit_id=visit_id, channel="telegram")

    fresh = sessionmaker(bind=pipeline_db)()
    try:
        visit = fresh.query(Visit).filter(Visit.id == visit_id).first()
        assert visit is not None
        assert visit.reminder_sent_at is None  # retry will re-attempt
    finally:
        fresh.close()


@pytest.mark.asyncio
async def test_worker_second_run_does_not_resend(
    pipeline_db, make_visit, reminder_spy
):
    """Criterion 5 (idempotency half): a repeat run — arq retry or duplicate
    enqueue — must not send a second notification."""
    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()
    await send_visit_reminder({}, visit_id=visit_id, channel="telegram")
    await send_visit_reminder({}, visit_id=visit_id, channel="telegram")

    assert len(reminder_spy) == 1  # second run skipped the send

    fresh = sessionmaker(bind=pipeline_db)()
    try:
        visit = fresh.query(Visit).filter(Visit.id == visit_id).first()
        first_stamp = visit.reminder_sent_at
        assert first_stamp is not None
    finally:
        fresh.close()

    # And a third run keeps both the send count and the stamp stable.
    await send_visit_reminder({}, visit_id=visit_id, channel="telegram")
    assert len(reminder_spy) == 1
    fresh2 = sessionmaker(bind=pipeline_db)()
    try:
        visit2 = fresh2.query(Visit).filter(Visit.id == visit_id).first()
        assert visit2.reminder_sent_at == first_stamp
    finally:
        fresh2.close()


# ---------------------------------------------------------------------------
# 4. Full business wiring via a REAL Redis queue (criterion 5)
# ---------------------------------------------------------------------------


@pytest.mark.redis
@pytest.mark.asyncio
async def test_reminder_end_to_end_via_real_clinic_queue(
    pipeline_db, make_visit, reminder_spy, monkeypatch: pytest.MonkeyPatch
):
    """Criterion 5 full proof: real enqueue onto the real 'clinic' queue →
    in-process burst arq worker picks the job up → notification service
    called once with the right args → reminder_sent_at stamped → a second
    forced delivery with a FRESH job ID (bypassing queue-level dedupe) does
    not resend. Skips when no Redis is reachable (CI provides a redis
    service container; requires no external worker consuming 'clinic')."""
    from arq import create_pool
    from arq.connections import RedisSettings
    from arq.constants import job_key_prefix, result_key_prefix
    from arq.jobs import Job
    from arq.worker import Worker

    from app.models.visit import Visit
    from app.tasks import enqueue_reminder
    from app.tasks.scheduler import _enqueue
    from app.tasks.worker import QUEUE_NAME, WorkerSettings

    if not _redis_reachable():
        pytest.skip("no Redis reachable — run with a redis service container")

    monkeypatch.setattr(settings, "ARQ_REDIS_URL", REDIS_URL)
    visit_id = make_visit()

    # Deterministic producer job ID — a leftover job hash from a previous
    # run (same visit number in a fresh temp DB!) makes enqueue_job return
    # None (dedupe) and the whole test would silently see zero deliveries.
    deterministic_job_id = f"reminder:visit:{visit_id}:telegram"

    pool = await create_pool(RedisSettings.from_dsn(REDIS_URL))

    async def _clean_slate() -> None:
        # arq dedupes on BOTH the job hash AND the retained result key
        # (enqueue_job checks job_key + arq:result:{job_id}) — a previous
        # run's completed result (TTL=keep_result) would otherwise make the
        # deterministic-ID enqueue silently return None.
        await pool.delete(
            QUEUE_NAME,
            f"{job_key_prefix}{deterministic_job_id}",
            f"{result_key_prefix}{deterministic_job_id}",
            f"{QUEUE_NAME}:stats",
            f"{QUEUE_NAME}:health-check",
        )

    try:
        await _clean_slate()

        # -- 1. REAL producer enqueue -------------------------------------
        job_id = await enqueue_reminder(visit_id=visit_id)
        assert job_id == deterministic_job_id
        assert await pool.exists(f"{job_key_prefix}{job_id}"), (
            "job must exist on the real queue after enqueue"
        )

        # -- 2. Worker picks it up, service called with right args --------
        worker = Worker(
            functions=WorkerSettings.functions,
            redis_pool=pool,
            queue_name=QUEUE_NAME,
            burst=True,
            poll_delay=0.05,
            job_timeout=30,
            keep_result=60,
            handle_signals=False,
            max_jobs=1,
            log_results=False,
        )
        await asyncio.wait_for(worker.async_run(), timeout=60)

        assert len(reminder_spy) == 1, (
            "burst worker must deliver exactly one service call"
        )
        assert reminder_spy[0]["visit_id"] == visit_id
        assert reminder_spy[0]["hours_before"] == 24
        # The job must have COMPLETED on the worker (a raise here would mean
        # the job failed and was rescheduled instead of processed).
        first_result = await asyncio.wait_for(
            Job(job_id, pool, _queue_name=QUEUE_NAME).result(timeout=10), timeout=15
        )
        assert first_result is None

        fresh = sessionmaker(bind=pipeline_db)()
        try:
            visit = fresh.query(Visit).filter(Visit.id == visit_id).first()
            assert visit.reminder_sent_at is not None
            first_stamp = visit.reminder_sent_at
        finally:
            fresh.close()

        # -- 3. Queue-level dedupe: deterministic job ID ------------------
        dup_id = await enqueue_reminder(visit_id=visit_id)
        assert dup_id == job_id  # same deterministic ID, honest skip

        # -- 4. DB-level idempotency: fresh job ID forces a real run ------
        retry_id = await _enqueue(
            "send_visit_reminder",
            visit_id=visit_id,
            channel="telegram",
            _job_id=f"reminder:visit:{visit_id}:telegram:e2e-retry-{uuid.uuid4().hex[:6]}",
        )
        worker2 = Worker(
            functions=WorkerSettings.functions,
            redis_pool=pool,
            queue_name=QUEUE_NAME,
            burst=True,
            poll_delay=0.05,
            job_timeout=30,
            keep_result=60,
            handle_signals=False,
            max_jobs=1,
            log_results=False,
        )
        await asyncio.wait_for(worker2.async_run(), timeout=60)

        assert len(reminder_spy) == 1, (
            "second delivery with a fresh job ID must NOT resend"
        )
        # The forced second job must have COMPLETED (clean skip, not a crash)
        result = await asyncio.wait_for(
            Job(retry_id, pool, _queue_name=QUEUE_NAME).result(timeout=10), timeout=15
        )
        assert result is None

        fresh2 = sessionmaker(bind=pipeline_db)()
        try:
            visit2 = fresh2.query(Visit).filter(Visit.id == visit_id).first()
            assert visit2.reminder_sent_at == first_stamp
        finally:
            fresh2.close()
    finally:
        try:
            await _clean_slate()
        except Exception:
            pass
        close = getattr(pool, "aclose", None) or pool.close
        await close()

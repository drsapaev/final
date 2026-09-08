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
import os
import socket
import sys
import tempfile
import uuid
from datetime import date
from urllib.parse import urlparse, urlsplit, urlunsplit

import pytest
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


def _test_redis_url() -> str:
    """Force every Redis touchpoint onto a disposable logical DB.

    The application queue lives in db 0 of ARQ_REDIS_URL; clearing the
    'clinic' queue there would silently destroy unrelated pending jobs on
    any shared/unauthenticated Redis reachable at the same address. Tests
    run on db 15 (the conventional pytest sandbox DB — the app never uses
    it), whatever host/port the environment points at.
    """
    raw = os.environ.get("ARQ_REDIS_URL") or "redis://localhost:6379"
    parts = urlsplit(raw)
    return urlunsplit((parts.scheme, parts.netloc, "/15", parts.query, parts.fragment))


REDIS_URL = _test_redis_url()

# Schedule version matching the make_visit fixture rows (date=today,
# time="10:00", generation=0). Codex round 7: every delivery MUST carry a
# schedule version — unversioned jobs are rejected by the worker.
FIXTURE_VERSION = f"{date.today().isoformat()}T10:00#0"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakePool:
    """Minimal arq pool stand-in capturing enqueue_job calls.

    ``job`` may be a single value or a LIST of per-call return values
    (Codex round 9, P2: the first enqueue can return None for a retained
    result and the retried attempt returns a real job). ``job_key_exists``
    mimics pool.exists(job_key_prefix + id): True = genuinely queued.
    """

    def __init__(
        self,
        job="job-ok",
        exc: Exception | None = None,
        job_key_exists: bool = True,
    ):
        self._jobs = list(job) if isinstance(job, list) else [job]
        self._exc = exc
        self.job_key_exists = job_key_exists
        self.exists_calls: list[str] = []
        self.calls: list[tuple[str, tuple, dict]] = []
        self.closed = False

    async def enqueue_job(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))
        if self._exc is not None:
            raise self._exc
        if len(self._jobs) > 1:
            return self._jobs.pop(0)
        return self._jobs[0]

    async def exists(self, key: str) -> bool:
        self.exists_calls.append(key)
        return self.job_key_exists

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
            # Synthetic-data policy (AGENTS.md): no real-looking
            # name+phone fixtures. Operator prefix 00 does not exist in
            # the +998 numbering plan and the address carries an explicit
            # SYNTHETIC marker, so the bundle cannot be mistaken for real
            # patient data.
            patient = Patient(
                first_name="Синтетик",
                last_name=f"Тест_{suffix}",
                middle_name="Синтетикович",
                phone=f"+998000{int(uuid.uuid4().int % 10**6):06d}",
                birth_date=date(1990, 1, 1),
                address="SYNTHETIC-REMINDER-PIPELINE-FIXTURE",
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

    job_id = await enqueue_reminder(visit_id=42, schedule_version="2026-09-08T10:00#0")

    assert job_id == "reminder:visit:42:2026-09-08T10:00#0:telegram"
    func, args, kwargs = pool.calls[0]
    assert func == "send_visit_reminder"
    assert args == ()
    assert kwargs["visit_id"] == 42
    assert kwargs["channel"] == "telegram"
    assert kwargs["_job_id"] == "reminder:visit:42:2026-09-08T10:00#0:telegram"
    assert kwargs["schedule_version"] == "2026-09-08T10:00#0"
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

    job_id = await enqueue_reminder(visit_id=7, schedule_version="2026-09-08T10:00#0")
    assert job_id == "reminder:visit:7:2026-09-08T10:00#0:telegram"


@pytest.mark.asyncio
async def test_enqueue_reminder_job_id_is_schedule_versioned(
    monkeypatch: pytest.MonkeyPatch,
):
    """Codex round 4, P1: a rescheduled visit must re-enqueue under a NEW
    job ID — arq retains a completed job's result for keep_result seconds,
    and during that window the old deterministic ID makes enqueue_job
    return None (nothing queued) while the reschedule already cleared the
    stamp: the new reminder would silently strand. Versioning by the
    schedule keeps same-schedule dedupe AND un-strands reschedules."""
    from app.tasks import enqueue_reminder

    pool = _FakePool()

    async def _fake_create_pool(redis_settings):
        return pool

    import arq

    monkeypatch.setattr(arq, "create_pool", _fake_create_pool)

    # A→B→A cycle (Codex round 7, P1): the GENERATION makes versions
    # immutable and never-repeating — every reschedule re-enqueues under a
    # fresh ID and can never collide with a retained arq result.
    id_a0 = await enqueue_reminder(visit_id=9, schedule_version="2026-09-08T10:00#0")
    id_b = await enqueue_reminder(visit_id=9, schedule_version="2026-09-10T10:00#1")
    id_a1 = await enqueue_reminder(visit_id=9, schedule_version="2026-09-08T10:00#2")
    assert id_a0 == "reminder:visit:9:2026-09-08T10:00#0:telegram"
    assert id_b == "reminder:visit:9:2026-09-10T10:00#1:telegram"
    assert id_a1 == "reminder:visit:9:2026-09-08T10:00#2:telegram"
    assert len({id_a0, id_b, id_a1}) == 3  # never collide with retained results

    # The version is REQUIRED (Codex round 7, P1): unversioned jobs cannot
    # be verified against the schedule and are rejected by the worker.
    with pytest.raises(TypeError):
        await enqueue_reminder(visit_id=9)


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
        await enqueue_reminder(visit_id=1, schedule_version="2026-09-08T10:00#0")


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
        await enqueue_reminder(visit_id=1, schedule_version="2026-09-08T10:00#0")


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
    await send_visit_reminder(
        {},
        visit_id=visit_id,
        channel="telegram",
        schedule_version=FIXTURE_VERSION,
    )

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
        assert visit.reminder_claimed_at is None  # lease released on finalize
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
    from arq.worker import Retry

    with pytest.raises(Retry):
        await send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=FIXTURE_VERSION,
        )

    fresh = sessionmaker(bind=pipeline_db)()
    try:
        visit = fresh.query(Visit).filter(Visit.id == visit_id).first()
        assert visit is not None
        assert visit.reminder_sent_at is None  # retry will re-attempt
        assert visit.reminder_claimed_at is None  # lease released on failure
    finally:
        fresh.close()


@pytest.mark.asyncio
async def test_worker_second_run_does_not_resend(pipeline_db, make_visit, reminder_spy):
    """Criterion 5 (idempotency half): a repeat run — arq retry or duplicate
    enqueue — must not send a second notification."""
    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()
    await send_visit_reminder(
        {},
        visit_id=visit_id,
        channel="telegram",
        schedule_version=FIXTURE_VERSION,
    )
    await send_visit_reminder(
        {},
        visit_id=visit_id,
        channel="telegram",
        schedule_version=FIXTURE_VERSION,
    )

    assert len(reminder_spy) == 1  # second run skipped the send

    fresh = sessionmaker(bind=pipeline_db)()
    try:
        visit = fresh.query(Visit).filter(Visit.id == visit_id).first()
        first_stamp = visit.reminder_sent_at
        assert first_stamp is not None
    finally:
        fresh.close()

    # And a third run keeps both the send count and the stamp stable.
    await send_visit_reminder(
        {},
        visit_id=visit_id,
        channel="telegram",
        schedule_version=FIXTURE_VERSION,
    )
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
    _vs = sessionmaker(bind=pipeline_db)()
    _visit_row = _vs.query(Visit).filter(Visit.id == visit_id).first()
    from app.tasks.scheduler import build_reminder_schedule_version

    schedule_version = build_reminder_schedule_version(_visit_row)
    _vs.close()
    deterministic_job_id = f"reminder:visit:{visit_id}:{schedule_version}:telegram"

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
        job_id = await enqueue_reminder(
            visit_id=visit_id, schedule_version=schedule_version
        )
        assert job_id == deterministic_job_id
        assert await pool.exists(
            f"{job_key_prefix}{job_id}"
        ), "job must exist on the real queue after enqueue"

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

        assert (
            len(reminder_spy) == 1
        ), "burst worker must deliver exactly one service call"
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

        # -- 3. Queue-level dedupe vs retained result (round 9) ----------
        # Step 2 COMPLETED this job: the job key is gone and the result is
        # retained. A same-ID re-enqueue now returns None and the scheduler
        # (round 9, P2) re-enqueues under an attempt suffix — the DB-level
        # idempotency still prevents a resend.
        dup_id = await enqueue_reminder(
            visit_id=visit_id, schedule_version=schedule_version
        )
        assert dup_id.startswith(
            job_id + ":attempt:"
        ), f"retained-result re-enqueue must use an attempt suffix: {dup_id}"
        assert await pool.exists(
            f"{job_key_prefix}{dup_id}"
        ), "the attempt job must be really queued"

        worker3 = Worker(
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
        await asyncio.wait_for(worker3.async_run(), timeout=60)
        assert (
            len(reminder_spy) == 1
        ), "the attempt job must not resend (already reminded)"

        # -- 4. DB-level idempotency: fresh job ID forces a real run ------
        retry_id = await _enqueue(
            "send_visit_reminder",
            visit_id=visit_id,
            channel="telegram",
            _job_id=(
                f"reminder:visit:{visit_id}:telegram:"
                f"e2e-retry-{uuid.uuid4().hex[:6]}"
            ),
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

        assert (
            len(reminder_spy) == 1
        ), "second delivery with a fresh job ID must NOT resend"
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


# ---------------------------------------------------------------------------
# 6. Reschedule invalidates the reminder stamp (Codex round 2, P1)
# ---------------------------------------------------------------------------


def _stamp_and_reschedule_setup(pipeline_db, make_visit):
    """Create a visit, stamp reminder_sent_at (as if already reminded),
    return (visit_id, session, new_date)."""
    from datetime import datetime, timedelta, UTC

    from app.models.visit import Visit

    visit_id = make_visit()
    s = sessionmaker(bind=pipeline_db)()
    stamped = datetime.now(UTC)
    s.query(Visit).filter(Visit.id == visit_id).update(
        {"reminder_sent_at": stamped, "reminder_claimed_at": stamped}
    )
    s.commit()
    return visit_id, s, date.today() + timedelta(days=3), stamped


def test_service_reschedule_clears_reminder_stamp(pipeline_db, make_visit):
    """Codex round 2 P1: the stamp is only valid for the CURRENT schedule.
    VisitsApiService.reschedule_visit must clear it — otherwise the next
    reminder job silently no-ops on the stale stamp and the patient never
    gets a reminder for the new date."""
    from app.models.visit import Visit
    from app.services.visits_api_service import VisitsApiService

    visit_id, s, new_date, stamped = _stamp_and_reschedule_setup(
        pipeline_db, make_visit
    )
    try:
        service = VisitsApiService(s)
        service.reschedule_visit(visit_id=visit_id, new_date=new_date)

        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.visit_date == new_date
        assert (
            row.reminder_sent_at is None
        ), "reschedule must invalidate the stale reminder stamp"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "reschedule must preserve the live lease (round 8)"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "reschedule must preserve the live lease (round 8), value intact"
    finally:
        s.close()


def test_reschedule_route_clears_reminder_stamp(pipeline_db, make_visit):
    """Same contract for the POST /visits/{visit_id}/reschedule route
    (it performs its own table update, independent of the service)."""
    from app.api.v1.endpoints.visits import reschedule_visit as reschedule_route
    from app.models.visit import Visit

    visit_id, s, new_date, stamped = _stamp_and_reschedule_setup(
        pipeline_db, make_visit
    )
    try:
        reschedule_route(visit_id=visit_id, new_date=new_date, new_time=None, db=s)

        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.visit_date == new_date
        assert (
            row.reminder_sent_at is None
        ), "reschedule route must invalidate the stale reminder stamp"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "reschedule route must preserve the live lease (round 8)"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "reschedule route must preserve the live lease (round 8), value intact"
    finally:
        s.close()


def test_reschedule_tomorrow_route_clears_reminder_stamp(pipeline_db, make_visit):
    """Same contract for POST /visits/{visit_id}/reschedule/tomorrow."""
    from datetime import timedelta

    from app.api.v1.endpoints.visits import (
        reschedule_visit_tomorrow as reschedule_tomorrow_route,
    )
    from app.models.visit import Visit

    visit_id, s, _new_date, stamped = _stamp_and_reschedule_setup(
        pipeline_db, make_visit
    )
    try:
        reschedule_tomorrow_route(visit_id=visit_id, db=s)

        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.visit_date == date.today() + timedelta(days=1)
        assert (
            row.reminder_sent_at is None
        ), "tomorrow-reschedule must invalidate the stale reminder stamp"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "tomorrow-reschedule must preserve the live lease (round 8)"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "tomorrow-reschedule must preserve the live lease (round 8), value intact"
    finally:
        s.close()


def test_telegram_move_visit_clears_reminder_stamp(pipeline_db, make_visit):
    """Codex round 3 P1: the Telegram /move_visit flow is a schedule change
    like any reschedule — TelegramStaffActionAdapterService.staff_move_visit
    must invalidate the stamp, otherwise the worker's conditional claim
    matches zero rows and the patient gets no reminder for the new date."""
    from app.models.audit import AuditLog
    from app.models.clinic import Doctor
    from app.models.visit import Visit
    from app.services.telegram_staff_action_adapter_service import (
        TelegramStaffActionAdapterService,
    )

    visit_id, s, new_date, stamped = _stamp_and_reschedule_setup(
        pipeline_db, make_visit
    )
    try:
        visit = s.query(Visit).filter(Visit.id == visit_id).first()
        actor_user_id = (
            s.query(Doctor).filter(Doctor.id == visit.doctor_id).first().user_id
        )

        service = TelegramStaffActionAdapterService(s)

        class _StubQueue:
            """The queue-link side effect is not under test here."""

            def staff_move_visit_queue_link(self, db, **kwargs):
                return {"status": "skipped", "queue_time_preserved": None}

        service.queue_service = _StubQueue()
        result = service.staff_move_visit(
            visit_id=visit_id,
            new_visit_date=new_date,
            actor_user_id=actor_user_id,
        )

        assert result["success"] is True
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.visit_date == new_date
        assert (
            row.reminder_sent_at is None
        ), "telegram move must invalidate the stale reminder stamp"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "telegram move must preserve the live lease (round 8)"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "telegram move must preserve the live lease (round 8), value intact"

        # Cleanup: audit rows written by this call reference the shared DB.
        s.query(AuditLog).filter(
            AuditLog.entity_id == visit_id, AuditLog.entity_type == "visit"
        ).delete()
        s.commit()
    finally:
        s.close()


def test_worker_failure_releases_only_own_claim(
    pipeline_db, make_visit, monkeypatch: pytest.MonkeyPatch
):
    """Codex round 3 P2: the release must only ever touch OUR OWN lease. If
    the lease changed between our claim and our failure (reschedule cleared
    it and another delivery re-claimed), releasing is a no-op and the newer
    lease survives — otherwise the next job would send a duplicate."""
    from datetime import datetime, timedelta, UTC

    from app.models.visit import Visit
    from app.services.notifications_pkg._reminders import RemindersMixin
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()
    newer_lease = datetime.now(UTC) + timedelta(minutes=1)

    async def _failing_spy(self, db, vid, hours_before=24):
        # A concurrent delivery re-claims while OUR dispatch is in flight
        # (reschedule cleared our lease, the newer job took its own).
        db.query(Visit).filter(Visit.id == vid).update(
            {"reminder_claimed_at": newer_lease}
        )
        db.commit()
        return {"success": False, "error": "telegram unavailable"}

    monkeypatch.setattr(RemindersMixin, "send_confirmation_reminder", _failing_spy)

    from arq.worker import Retry

    with pytest.raises(Retry):
        asyncio.run(
            send_visit_reminder(
                {},
                visit_id=visit_id,
                channel="telegram",
                schedule_version=FIXTURE_VERSION,
            )
        )

    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        # sqlite round-trips DATETIME as naive — compare tz-stripped; the
        # essential assertions: our compensation did NOT erase the newer
        # delivery's lease, and no delivery was recorded by either job.
        assert row.reminder_sent_at is None, "no delivery may be recorded"
        assert (
            row.reminder_claimed_at is not None
        ), "compensation must not erase a newer delivery's lease"
        assert row.reminder_claimed_at == newer_lease.replace(
            tzinfo=None
        ), f"newer lease must survive: {row.reminder_claimed_at!r}"
    finally:
        s.close()


def test_expired_lease_is_reclaimed_after_crash(pipeline_db, make_visit, reminder_spy):
    """Codex round 4, P1 (crash recovery): a lease left behind by a killed
    worker — no compensation ran — must not strand the reminder forever.
    Once LEASE_TTL passes, a retry re-claims, delivers, and records."""
    from datetime import datetime, timedelta, UTC

    from app.models.visit import Visit
    from app.tasks.worker import LEASE_TTL, send_visit_reminder

    visit_id = make_visit()
    stale = datetime.now(UTC) - LEASE_TTL - timedelta(minutes=1)
    s = sessionmaker(bind=pipeline_db)()
    s.query(Visit).filter(Visit.id == visit_id).update({"reminder_claimed_at": stale})
    s.commit()
    s.close()

    asyncio.run(
        send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=FIXTURE_VERSION,
        )
    )

    assert len(reminder_spy) == 1, "stale lease must be reclaimable"
    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is not None
        assert row.reminder_claimed_at is None
    finally:
        s.close()


def test_live_lease_blocks_reclaim(pipeline_db, make_visit, reminder_spy):
    """The inverse of crash recovery: a LIVE lease (fresh claim, dispatch
    still in flight in another worker) must NOT be stolen by an overlapping
    delivery — exactly one dispatch per visit."""
    from datetime import datetime, UTC

    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()
    fresh = datetime.now(UTC)
    s = sessionmaker(bind=pipeline_db)()
    s.query(Visit).filter(Visit.id == visit_id).update({"reminder_claimed_at": fresh})
    s.commit()
    s.close()

    # Codex round 5, P1: a live lease must not merely skip — the job must
    # DEFER (raise arq Retry) so a redelivery actually comes back after the
    # lease resolves instead of completing and never returning.
    from arq.worker import Retry

    with pytest.raises(Retry):
        asyncio.run(
            send_visit_reminder(
                {},
                visit_id=visit_id,
                channel="telegram",
                schedule_version=FIXTURE_VERSION,
            )
        )

    assert reminder_spy == [], "a live lease must block a second delivery"
    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is None
        assert row.reminder_claimed_at == fresh.replace(tzinfo=None)
    finally:
        s.close()


def test_claim_rejects_visits_not_pending_confirmation(
    pipeline_db, make_visit, reminder_spy
):
    """Codex round 4, P1: the claim is restricted to the reminder-eligible
    lifecycle status — a visit that is already confirmed, closed, or
    canceled must never receive an obsolete confirmation request with
    actionable buttons."""
    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    for status in ("confirmed", "closed", "canceled"):
        visit_id = make_visit()
        s = sessionmaker(bind=pipeline_db)()
        s.query(Visit).filter(Visit.id == visit_id).update({"status": status})
        s.commit()
        s.close()

        asyncio.run(
            send_visit_reminder(
                {},
                visit_id=visit_id,
                channel="telegram",
                schedule_version=FIXTURE_VERSION,
            )
        )

        s = sessionmaker(bind=pipeline_db)()
        try:
            row = s.query(Visit).filter(Visit.id == visit_id).first()
            assert row.reminder_sent_at is None
            assert row.reminder_claimed_at is None
        finally:
            s.close()

    assert reminder_spy == [], "non-eligible visits must never dispatch"


def test_matching_schedule_version_delivers(pipeline_db, make_visit, reminder_spy):
    """Codex round 5, P1 happy path: the job's schedule version matches the
    visit's current date — the claim succeeds and the delivery happens."""
    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()  # visit_date = today, visit_time = "10:00"
    asyncio.run(
        send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=FIXTURE_VERSION,
        )
    )

    assert len(reminder_spy) == 1
    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is not None
        assert row.reminder_claimed_at is None
    finally:
        s.close()


def test_stale_schedule_version_is_rejected(pipeline_db, make_visit, reminder_spy):
    """Codex round 5, P1: a stale job (enqueued for the OLD schedule before
    a reschedule) must never claim, dispatch, or stamp — otherwise it
    delivers for the obsolete schedule and the correctly timed job skips."""
    from datetime import timedelta

    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()  # visit_date = today, visit_time = "10:00"
    stale_version = f"{(date.today() - timedelta(days=2)).isoformat()}T10:00#0"

    asyncio.run(
        send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=stale_version,
        )
    )

    assert reminder_spy == [], "a stale job must never dispatch"
    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is None
        assert row.reminder_claimed_at is None
    finally:
        s.close()


def test_noop_reschedule_preserves_reminder_state(pipeline_db, make_visit):
    """Codex round 5, P2: a reschedule to the SAME date (client retry,
    same-value re-submit) must PRESERVE the reminder state — clearing it
    would let a later job duplicate a reminder for the identical
    appointment."""
    from datetime import datetime, UTC

    from app.models.visit import Visit
    from app.services.visits_api_service import VisitsApiService

    visit_id = make_visit()
    s = sessionmaker(bind=pipeline_db)()
    try:
        stamped = datetime.now(UTC)
        s.query(Visit).filter(Visit.id == visit_id).update(
            {"reminder_sent_at": stamped, "reminder_claimed_at": stamped}
        )
        s.commit()

        current_date = s.query(Visit).filter(Visit.id == visit_id).first().visit_date
        service = VisitsApiService(s)
        service.reschedule_visit(visit_id=visit_id, new_date=current_date)

        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.visit_date == current_date
        assert row.reminder_sent_at == stamped.replace(
            tzinfo=None
        ), "no-op reschedule must not clear the reminder stamp"
        assert row.reminder_claimed_at == stamped.replace(
            tzinfo=None
        ), "no-op reschedule must not clear the lease"
        assert (
            row.reminder_generation == 0
        ), "no-op reschedule must not bump the generation"
    finally:
        s.close()


def test_noop_reschedule_route_preserves_reminder_state(pipeline_db, make_visit):
    """Same no-op contract for the POST /visits/{id}/reschedule route."""
    from datetime import datetime, UTC

    from app.api.v1.endpoints.visits import reschedule_visit as reschedule_route
    from app.models.visit import Visit

    visit_id = make_visit()
    s = sessionmaker(bind=pipeline_db)()
    try:
        stamped = datetime.now(UTC)
        s.query(Visit).filter(Visit.id == visit_id).update(
            {"reminder_sent_at": stamped, "reminder_claimed_at": stamped}
        )
        s.commit()

        current_date = s.query(Visit).filter(Visit.id == visit_id).first().visit_date
        reschedule_route(visit_id=visit_id, new_date=current_date, new_time=None, db=s)

        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.visit_date == current_date
        assert row.reminder_sent_at == stamped.replace(tzinfo=None)
        assert row.reminder_claimed_at == stamped.replace(tzinfo=None)
    finally:
        s.close()


def test_noop_move_preserves_reminder_state(pipeline_db, make_visit):
    """Same no-op contract for the Telegram /move_visit adapter."""
    from datetime import datetime, UTC

    from app.models.audit import AuditLog
    from app.models.clinic import Doctor
    from app.models.visit import Visit
    from app.services.telegram_staff_action_adapter_service import (
        TelegramStaffActionAdapterService,
    )

    visit_id = make_visit()
    s = sessionmaker(bind=pipeline_db)()
    try:
        stamped = datetime.now(UTC)
        s.query(Visit).filter(Visit.id == visit_id).update(
            {"reminder_sent_at": stamped, "reminder_claimed_at": stamped}
        )
        s.commit()

        visit = s.query(Visit).filter(Visit.id == visit_id).first()
        actor_user_id = (
            s.query(Doctor).filter(Doctor.id == visit.doctor_id).first().user_id
        )
        current_date = visit.visit_date

        service = TelegramStaffActionAdapterService(s)

        class _StubQueue:
            def staff_move_visit_queue_link(self, db, **kwargs):
                return {"status": "skipped", "queue_time_preserved": None}

        service.queue_service = _StubQueue()
        result = service.staff_move_visit(
            visit_id=visit_id,
            new_visit_date=current_date,
            actor_user_id=actor_user_id,
        )

        assert result["success"] is True
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.visit_date == current_date
        assert row.reminder_sent_at == stamped.replace(tzinfo=None)
        assert row.reminder_claimed_at == stamped.replace(tzinfo=None)

        s.query(AuditLog).filter(
            AuditLog.entity_id == visit_id, AuditLog.entity_type == "visit"
        ).delete()
        s.commit()
    finally:
        s.close()


def test_stale_time_version_is_rejected(pipeline_db, make_visit, reminder_spy):
    """Codex round 6, P1: the schedule version covers date AND time — a
    time-only reschedule (same date, new visit_time) must invalidate the
    version, so a stale job enqueued for the old time can neither claim,
    dispatch, nor stamp."""
    from datetime import date

    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()  # visit_date = today, visit_time = "10:00"
    stale_version = f"{date.today().isoformat()}T09:00#0"

    asyncio.run(
        send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=stale_version,
        )
    )

    assert reminder_spy == [], "a stale time-only version must not dispatch"
    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is None
        assert row.reminder_claimed_at is None
    finally:
        s.close()


def test_stale_generation_is_rejected(pipeline_db, make_visit, reminder_spy):
    """Codex round 7, P1: the generation binds the claim. After a
    reschedule bumps the generation, an old job carrying the previous
    generation must be rejected even with matching date and time."""
    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()  # generation = 0
    stale_gen_version = f"{date.today().isoformat()}T10:00#5"

    asyncio.run(
        send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=stale_gen_version,
        )
    )

    assert reminder_spy == [], "a stale generation must not dispatch"
    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is None
        assert row.reminder_claimed_at is None
    finally:
        s.close()


def test_unversioned_job_is_rejected(pipeline_db, make_visit, reminder_spy):
    """Codex round 7, P1: unversioned jobs cannot be verified against the
    current schedule and are rejected outright — the schedule_version is a
    REQUIRED producer argument."""
    from app.models.visit import Visit
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()

    asyncio.run(send_visit_reminder({}, visit_id=visit_id, channel="telegram"))

    assert reminder_spy == [], "an unversioned job must not dispatch"
    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is None
        assert row.reminder_claimed_at is None
    finally:
        s.close()


def test_reschedule_during_dispatch_prevents_stale_record(
    pipeline_db, make_visit, monkeypatch: pytest.MonkeyPatch
):
    """Codex round 8, P1: a reschedule landing while a delivery is in
    flight bumps the generation and preserves the lease. The in-flight
    worker's finalize is generation-guarded: its OLD-schedule delivery is
    NOT recorded (only the lease is released), and the new generation's
    job can then claim and deliver for the new schedule."""
    import asyncio

    from app.models.visit import Visit
    from app.services.notifications_pkg._reminders import RemindersMixin
    from app.tasks.scheduler import build_reminder_schedule_version
    from app.tasks.worker import send_visit_reminder

    visit_id = make_visit()  # generation 0, date today, time "10:00"

    async def _spy(self, db, vid, hours_before=24):
        # The reschedule lands while the provider call is in flight:
        # stamp cleared, generation bumped, lease PRESERVED (round 8).
        db.query(Visit).filter(Visit.id == vid).update(
            {"reminder_sent_at": None, "reminder_generation": 1}
        )
        db.commit()
        return {"success": True, "channel": "telegram"}

    monkeypatch.setattr(RemindersMixin, "send_confirmation_reminder", _spy)

    # Old-generation delivery: the provider accepts, but the finalize must
    # refuse to record it (generation moved on underneath the dispatch).
    old_version = f"{date.today().isoformat()}T10:00#0"
    asyncio.run(
        send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=old_version,
        )
    )

    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_generation == 1
        assert (
            row.reminder_sent_at is None
        ), "an old-schedule delivery must not be recorded after a reschedule"
        assert (
            row.reminder_claimed_at is None
        ), "the in-flight worker must release the lease at finalize"
    finally:
        s.close()

    # The new generation's job now delivers AND records.
    s = sessionmaker(bind=pipeline_db)()
    try:
        fresh = s.query(Visit).filter(Visit.id == visit_id).first()
        new_version = build_reminder_schedule_version(fresh)
    finally:
        s.close()

    asyncio.run(
        send_visit_reminder(
            {},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=new_version,
        )
    )

    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert (
            row.reminder_sent_at is not None
        ), "the new generation must deliver and record"
        assert row.reminder_claimed_at is None
    finally:
        s.close()


@pytest.mark.asyncio
async def test_delivery_failure_gives_up_after_backoffs(
    pipeline_db, make_visit, monkeypatch: pytest.MonkeyPatch
):
    """Codex round 9, P1: after the three deferred attempts the failure
    becomes permanent (RuntimeError) — the reminder is recorded as
    permanently failed, lease released, stamp still NULL."""
    from app.models.visit import Visit
    from app.services.notifications_pkg._reminders import RemindersMixin
    from app.tasks.worker import send_visit_reminder

    async def _failing(self, db, visit_id, hours_before=24):
        return {"success": False, "error": "telegram unavailable"}

    monkeypatch.setattr(RemindersMixin, "send_confirmation_reminder", _failing)

    visit_id = make_visit()
    with pytest.raises(RuntimeError, match="Notification send failed"):
        await send_visit_reminder(
            {"job_try": 4},
            visit_id=visit_id,
            channel="telegram",
            schedule_version=FIXTURE_VERSION,
        )

    s = sessionmaker(bind=pipeline_db)()
    try:
        row = s.query(Visit).filter(Visit.id == visit_id).first()
        assert row.reminder_sent_at is None
        assert row.reminder_claimed_at is None
    finally:
        s.close()


@pytest.mark.asyncio
async def test_enqueue_retained_result_requeues_with_attempt_suffix(
    monkeypatch: pytest.MonkeyPatch,
):
    """Codex round 9, P2: enqueue_job returning None is ambiguous — it may
    be a retained RESULT (job not on the queue anymore) rather than a live
    duplicate. A failed delivery leaves the generation unchanged, so a
    re-enqueue for the same schedule reuses the failed job's ID and must
    NOT be treated as an honest skip. The scheduler inspects the live job
    key and retries under a unique attempt suffix."""
    from app.tasks import enqueue_reminder

    # First enqueue hits a retained result (None) with NO live job key;
    # the retried attempt lands on the queue and returns a real job.
    pool = _FakePool(job=[None, "job-attempt"], job_key_exists=False)

    async def _fake_create_pool(redis_settings):
        return pool

    import arq

    monkeypatch.setattr(arq, "create_pool", _fake_create_pool)

    job_id = await enqueue_reminder(visit_id=11, schedule_version="2026-09-08T10:00#0")
    assert job_id.startswith(
        "reminder:visit:11:2026-09-08T10:00#0:telegram:attempt:"
    ), f"expected attempt-suffixed id, got {job_id}"
    assert len(pool.exists_calls) == 1  # exactly one ambiguity check
    assert len(pool.calls) == 2  # original + attempt retry
    assert pool.calls[1][2]["_job_id"] == job_id
    assert pool.closed

    # Genuinely queued duplicate: live job key exists -> honest skip.
    pool2 = _FakePool(job=None, job_key_exists=True)

    async def _fake_create_pool2(redis_settings):
        return pool2

    monkeypatch.setattr(arq, "create_pool", _fake_create_pool2)
    dup_id = await enqueue_reminder(visit_id=11, schedule_version="2026-09-08T10:00#0")
    assert dup_id == "reminder:visit:11:2026-09-08T10:00#0:telegram"
    assert pool2.exists_calls and len(pool2.calls) == 1  # no second enqueue


def test_claim_still_valid_rechecks_status_and_schedule():
    """Codex round 10, P1: the post-claim revalidation rechecks the
    lifecycle status alongside the full schedule version — a confirmation
    or cancellation committing between claim and dispatch aborts before
    any send."""
    from types import SimpleNamespace

    from app.tasks.worker import _claim_still_valid

    def _visit(status="pending_confirmation", vdate=None, vtime="10:00", gen=0):
        from datetime import date as _date

        return SimpleNamespace(
            status=status,
            visit_date=vdate or _date.today(),
            visit_time=vtime,
            reminder_generation=gen,
        )

    version = f"{date.today().isoformat()}T10:00#0"
    assert _claim_still_valid(_visit(), version) is True
    assert _claim_still_valid(_visit(status="confirmed"), version) is False
    assert _claim_still_valid(_visit(status="canceled"), version) is False
    assert _claim_still_valid(_visit(status="closed"), version) is False
    assert _claim_still_valid(None, version) is False
    assert (
        _claim_still_valid(_visit(vtime="09:00"), version) is False
    ), "a time change must invalidate the claim"
    assert (
        _claim_still_valid(_visit(gen=3), version) is False
    ), "a generation bump must invalidate the claim"


def test_transient_database_failure_defers(pipeline_db, make_visit, monkeypatch):
    """Codex round 10, P1: a transient database outage during the claim
    must defer the job (arq Retry), not permanently drop the reminder —
    only Retry/RetryJob/cancellation are requeued by arq 0.28."""
    from datetime import timedelta

    from app.core.config import settings
    from app.tasks.worker import send_visit_reminder

    make_visit()  # unused row on the real test DB
    # Point the worker at a fresh sqlite file with NO tables: the claim's
    # UPDATE raises OperationalError (a DBAPIError) — the canonical
    # transient database failure shape.
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    broken_url = f"sqlite:///{path}"
    monkeypatch.setattr(settings, "DATABASE_URL", broken_url)

    from arq.worker import Retry

    # The DBAPIError raised by the claim is translated to an arq Retry
    # (defer 10s on the first attempt) — the job is deferred, not dropped.
    with pytest.raises(Retry):
        asyncio.run(
            send_visit_reminder(
                {},
                visit_id=1,
                channel="telegram",
                schedule_version=(
                    f"{(date.today() + timedelta(days=1)).isoformat()}T" f"10:00#0"
                ),
            )
        )
    os.remove(path)

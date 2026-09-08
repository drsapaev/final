"""
arq worker entry point — real wiring (P2.3).

Run with:
    cd backend && arq app.tasks.worker.WorkerSettings

Or via docker-compose (ops/docker-compose.yml worker service).

The worker consumes the single 'clinic' queue (QUEUE_NAME — the same queue
name app/tasks/scheduler.py enqueues onto; the queue must never diverge)
on the Redis instance configured by settings.ARQ_REDIS_URL.

Jobs are defined as async functions in this file. The scheduler in
app/tasks/scheduler.py enqueues them by name.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

from arq import cron
from arq.connections import RedisSettings

# Ensure backend/ is on PYTHONPATH when run via `arq app.tasks.worker.WorkerSettings`
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)

# Lease must comfortably outlive the worst dispatch: arq's job_timeout
# is 300s, so a 10-minute TTL can only expire for a DEAD worker, never
# for a live one still awaiting the provider.
LEASE_TTL = timedelta(minutes=10)


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

def _schedule_matches(visit, schedule_version: str) -> bool:
    """True when the visit's current date+time still match the schedule
    version the job was enqueued for (format "{date}T{time}", "-" if the
    visit has no time)."""
    from datetime import date

    date_part, _, time_part = schedule_version.partition("T")
    if visit.visit_date != date.fromisoformat(date_part):
        return False
    if not time_part or time_part == "-":
        return visit.visit_time is None
    return visit.visit_time == time_part


async def send_visit_reminder(
    ctx,
    *,
    visit_id: int,
    channel: str = "telegram",
    schedule_version: str | None = None,
) -> None:
    """Send a reminder to a patient about an upcoming visit.

    Enqueued by app.tasks.scheduler.enqueue_reminder().

    Delivery protocol (Codex rounds 2-5): a short atomic lease claim bound
    to the visit's CURRENT schedule, the provider dispatch OUTSIDE any
    transaction/lock, and the permanent ``reminder_sent_at`` record only
    AFTER the provider acknowledges.

    1. Lease claim — one conditional UPDATE stamps ``reminder_claimed_at``
       only for a reminder-eligible visit (status ``pending_confirmation``,
       never reminded, no live lease; a lease older than LEASE_TTL belongs
       to a dead worker and is reclaimable). When the producer supplied a
       ``schedule_version`` (the schedule the job was enqueued for), the
       claim ALSO binds to ``visit_date == schedule_version`` — a stale job
       left queued by a reschedule can never deliver for the old schedule
       (Codex round 5, P1). The row lock lives ONLY for this statement —
       never across the notification await. Two overlapping deliveries can
       never both claim (proven against real PostgreSQL by
       tests/integration/test_reminder_pipeline_pg.py, gate_d marker).
    2. Dispatch — NotificationSenderService.send_confirmation_reminder()
       by its real contract. A crash between claim and dispatch leaves a
       lease that expires: the arq retry re-claims and delivers — the
       reminder is never stranded by a crash (Codex round 4, P1). An
       overlapping delivery hitting a LIVE lease raises arq ``Retry`` so
       the redelivery is deferred until the lease resolves instead of
       completing and never coming back (Codex round 5, P1). The residual
       at-least-once window (crash AFTER the provider accepted but BEFORE
       the record) is inherent to external sends without a provider-side
       idempotency key.
    3. Finalize — ``reminder_sent_at`` is recorded and the lease released
       in one statement bound to OUR lease value, so a concurrent
       reschedule/re-claim can never be overwritten by this job (Codex
       round 3, P2). On failure the lease is released the same way and
       arq retries.
    """
    from sqlalchemy import create_engine, func, or_, update
    from sqlalchemy.orm import Session

    from datetime import date

    from app.models.visit import Visit
    from app.services.notification_service import NotificationService

    logger.info(
        "job.send_visit_reminder visit_id=%s channel=%s schedule_version=%s",
        visit_id, channel, schedule_version,
    )

    engine = create_engine(str(settings.DATABASE_URL))
    db = Session(engine)
    # Python-side clock: the lease value must be byte-identical between the
    # claim write and the later equality guards on every dialect (a SQL
    # now() + RETURNING round-trip is fragile on SQLite, where
    # CURRENT_TIMESTAMP is second-precision TEXT).
    our_lease: datetime | None = None
    try:
        our_lease = datetime.now(UTC)
        conditions = [
            Visit.id == visit_id,
            Visit.status == "pending_confirmation",
            Visit.reminder_sent_at.is_(None),
            or_(
                Visit.reminder_claimed_at.is_(None),
                Visit.reminder_claimed_at < our_lease - LEASE_TTL,
            ),
        ]
        if schedule_version is not None:
            # Bind the claim to the FULL schedule this job was enqueued FOR
            # (date AND time — Codex rounds 5+6, P1): a stale job left
            # queued by a reschedule must never deliver for the old
            # schedule, and a time-only move invalidates the version too.
            # Format: "{visit_date.isoformat()}T{visit_time}" where an
            # absent time is the literal "-".
            date_part, _, time_part = schedule_version.partition("T")
            conditions.append(Visit.visit_date == date.fromisoformat(date_part))
            if time_part and time_part != "-":
                conditions.append(Visit.visit_time == time_part)
            else:
                conditions.append(Visit.visit_time.is_(None))
        claim = db.execute(
            update(Visit).where(*conditions).values(reminder_claimed_at=our_lease)
        )
        db.commit()
        if claim.rowcount == 0:
            our_lease = None
            visit = db.query(Visit).filter(Visit.id == visit_id).first()
            if not visit:
                logger.warning(
                    "job.send_visit_reminder: visit %s not found", visit_id
                )
                return
            if schedule_version is not None and not _schedule_matches(
                visit, schedule_version
            ):
                logger.info(
                    "job.send_visit_reminder: visit %s schedule moved on "
                    "(job version %s, visit %s %s) — stale job, skipping",
                    visit_id, schedule_version, visit.visit_date,
                    visit.visit_time,
                )
                return
            if visit.status != "pending_confirmation":
                logger.info(
                    "job.send_visit_reminder: visit %s not pending "
                    "confirmation (status=%s), skipping",
                    visit_id, visit.status,
                )
                return
            if visit.reminder_sent_at is not None:
                logger.info(
                    "job.send_visit_reminder: visit %s already reminded "
                    "at %s, skipping",
                    visit_id, visit.reminder_sent_at,
                )
                return
            # The only remaining reason the claim lost: a LIVE lease held by
            # another delivery. Returning cleanly would end this attempt AND
            # leave nothing to retry after the lease resolves — if the owner
            # then died, the reminder would strand forever (Codex round 5,
            # P1). Defer THIS job until shortly after the observed lease can
            # have expired; arq will re-run us to claim or re-defer.
            from arq.worker import Retry

            claimed_at = visit.reminder_claimed_at
            if claimed_at is not None:
                claimed_at = claimed_at.replace(tzinfo=UTC)
                defer = max(
                    30.0,
                    min(
                        (claimed_at + LEASE_TTL - datetime.now(UTC)).total_seconds(),
                        LEASE_TTL.total_seconds(),
                    ),
                )
            else:
                defer = LEASE_TTL.total_seconds()
            logger.info(
                "job.send_visit_reminder: visit %s has a live lease "
                "(claimed_at=%s), deferring redelivery by %.0fs",
                visit_id, visit.reminder_claimed_at, defer,
            )
            raise Retry(defer=defer)

        service = NotificationService(db)
        result = await service.send_confirmation_reminder(db, visit_id, hours_before=24)

        if not result.get("success"):
            logger.warning(
                "job.send_visit_reminder: send failed for visit %s: %s",
                visit_id, result.get("error", "unknown"),
            )
            # Release the lease in the handler below — let arq retry.
            raise RuntimeError(f"Notification send failed: {result.get('error')}")

        # Record the delivery only now — the provider acknowledged it — and
        # release the lease in the same statement, bound to OUR lease value.
        finalized = db.execute(
            update(Visit)
            .where(Visit.id == visit_id, Visit.reminder_claimed_at == our_lease)
            .values(reminder_sent_at=func.now(), reminder_claimed_at=None)
        )
        db.commit()
        if finalized.rowcount == 0:
            logger.warning(
                "job.send_visit_reminder: lease for visit %s was no longer "
                "ours at finalize; delivery not recorded",
                visit_id,
            )
        else:
            logger.info(
                "job.send_visit_reminder: visit %s reminded via %s",
                visit_id, result.get("channel", channel),
            )
    except Exception:
        # Rollback first — the failed service call may have left uncommitted
        # partial state on the session. Then release ONLY OUR OWN lease (the
        # equality predicate makes this a no-op once a reschedule cleared it
        # or a newer delivery re-claimed) so arq's retry can re-deliver.
        db.rollback()
        if our_lease is not None:
            db.execute(
                update(Visit)
                .where(Visit.id == visit_id, Visit.reminder_claimed_at == our_lease)
                .values(reminder_claimed_at=None)
            )
            db.commit()
        logger.exception("job.send_visit_reminder failed for visit %s", visit_id)
        raise
    finally:
        db.close()


async def run_data_retention(ctx) -> None:
    """Run the daily data retention cleanup. See data_retention.run_scheduled_cleanup."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.services.data_retention import run_scheduled_cleanup

    logger.info("job.run_data_retention starting")
    engine = create_engine(str(settings.DATABASE_URL))
    db = Session(engine)
    try:
        result = run_scheduled_cleanup(db)
        logger.info("job.run_data_retention complete: %s", result)
    finally:
        db.close()


async def generate_scheduled_report(ctx, *, report_type: str, filters: dict | None = None) -> None:
    """Generate a scheduled report. See reporting_service."""
    logger.info("job.generate_scheduled_report type=%s filters=%s", report_type, list((filters or {}).keys()))
    # TODO: wire to actual reporting_service.generate_scheduled_report
    # For now, log and complete successfully.
    await asyncio.sleep(0.1)
    logger.info("job.generate_scheduled_report complete (stub)")


async def run_lab_follow_up_reminders(ctx) -> None:
    """Send lab follow-up reminders. See lab_notification_service.send_follow_up_reminders.

    Runs daily — checks for lab orders with upcoming follow-up dates and
    sends reminders to patients 3 days before the scheduled follow-up.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import Session

    from app.services.lab_notification_service import LabNotificationService

    logger.info("job.run_lab_follow_up_reminders starting")
    engine = create_engine(str(settings.DATABASE_URL))
    db = Session(engine)
    try:
        svc = LabNotificationService(db)
        result = await svc.send_follow_up_reminders(days_before=3)
        logger.info("job.run_lab_follow_up_reminders complete: %s", result)
    except Exception:
        db.rollback()
        logger.exception("job.run_lab_follow_up_reminders failed")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Worker lifecycle
# ---------------------------------------------------------------------------

async def startup(ctx) -> None:
    logger.info("arq.worker.startup redis=%s", _redact_redis_url(settings.ARQ_REDIS_URL))


async def shutdown(ctx) -> None:
    logger.info("arq.worker.shutdown")


def _redact_redis_url(url: str) -> str:
    """Hide password in logs."""
    if "@" in url:
        scheme, rest = url.split("://", 1)
        creds, host = rest.split("@", 1)
        if ":" in creds:
            user, _pw = creds.split(":", 1)
            return f"{scheme}://{user}:***@{host}"
    return url


# ---------------------------------------------------------------------------
# Retry policy
# ---------------------------------------------------------------------------

async def retry_policy(ctx, exc_type, exc, task):
    """Retry up to 3 times with exponential backoff: 10s, 60s, 300s."""
    retry_count = ctx.get("job_try", 0)
    if retry_count >= 3:
        logger.error("retry_policy: giving up after %d tries on %s: %s", retry_count, task, exc)
        return False
    backoff = [10, 60, 300][min(retry_count, 2)]
    logger.warning("retry_policy: retry %d in %ds for %s", retry_count + 1, backoff, task)
    return backoff


# ---------------------------------------------------------------------------
# Worker settings — entry point for `arq` CLI
# ---------------------------------------------------------------------------

def _parse_redis_settings(url: str) -> RedisSettings:
    """Parse redis://[:password@]host:port/db into RedisSettings."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6379,
        password=parsed.password,
        database=int((parsed.path or "/0").lstrip("/") or "0"),
    )


# The single application queue. SSOT for both sides of the pipeline:
# the worker consumes this queue (WorkerSettings.queue_name) and the
# scheduler enqueues onto it (_queue_name=QUEUE_NAME) — previously the
# scheduler silently fell back to arq's default 'arq:queue' while the
# worker listened here, so every reminder was stranded.
QUEUE_NAME = "clinic"


class WorkerSettings:
    """arq worker configuration. Run with:
        arq app.tasks.worker.WorkerSettings
    """

    functions = [send_visit_reminder, run_data_retention, generate_scheduled_report, run_lab_follow_up_reminders]

    on_startup = startup
    on_shutdown = shutdown
    retry_policy = retry_policy

    redis_settings = _parse_redis_settings(settings.ARQ_REDIS_URL)

    max_jobs = 10
    job_timeout = 300  # 5 min per job
    health_check_interval = 30
    queue_name = QUEUE_NAME

    # Cron jobs — run on the schedule, regardless of enqueues
    cron_jobs = [
        cron(run_data_retention, hour=3, minute=0),  # Daily 03:00 UTC
        cron(run_lab_follow_up_reminders, hour=8, minute=0),  # Daily 08:00 UTC
    ]


# Make functions importable from app.tasks (for scheduler.py)
__all__ = [
    "QUEUE_NAME",
    "send_visit_reminder",
    "run_data_retention",
    "generate_scheduled_report",
    "run_lab_follow_up_reminders",
]

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
from pathlib import Path

from arq import cron
from arq.connections import RedisSettings

# Ensure backend/ is on PYTHONPATH when run via `arq app.tasks.worker.WorkerSettings`
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.core.config import settings  # noqa: E402

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Job implementations
# ---------------------------------------------------------------------------

async def send_visit_reminder(ctx, *, visit_id: int, channel: str = "telegram") -> None:
    """Send a reminder to a patient about an upcoming visit.

    Enqueued by app.tasks.scheduler.enqueue_reminder().
    Idempotent at the DB level: ``visits.reminder_sent_at`` (ORM column,
    migration 0060) is stamped on success, so arq retries and duplicate
    enqueues never send a second notification.

    Calls the real notification service by its actual contract:
    ``NotificationSenderService.send_confirmation_reminder(db, visit_id,
    hours_before=...)`` — the service re-resolves the visit and dispatches
    to Telegram/PWA/phone via _determine_best_channel(). The ``channel``
    argument of this job is a hint for logging only (the service owns the
    channel decision).
    """
    from sqlalchemy import create_engine, func, update
    from sqlalchemy.orm import Session

    from app.models.visit import Visit
    from app.services.notification_service import NotificationService

    logger.info("job.send_visit_reminder visit_id=%s channel=%s", visit_id, channel)

    engine = create_engine(str(settings.DATABASE_URL))
    db = Session(engine)
    claimed = False
    try:
        # Phase 1 — short atomic claim (Codex round 2, P2): one conditional
        # UPDATE takes the idempotency stamp. The row lock lives ONLY for
        # this statement — it is never held across the notification await
        # (a slow Telegram/PWA call must not block concurrent reschedules,
        # cancellations or status writes on the same visit). A concurrent
        # delivery's UPDATE blocks until this commits, then re-evaluates
        # ``reminder_sent_at IS NULL`` and matches 0 rows — two overlapping
        # jobs can never both dispatch. The PostgreSQL race is proven by
        # tests/integration/test_reminder_pipeline_pg.py (gate_d marker);
        # the sequential contract lives in test_reminder_pipeline.py.
        claim = db.execute(
            update(Visit)
            .where(Visit.id == visit_id, Visit.reminder_sent_at.is_(None))
            .values(reminder_sent_at=func.now())
        )
        db.commit()
        if claim.rowcount == 0:
            # Either the visit is gone or a concurrent delivery won the
            # claim — distinguish for honest logs.
            exists = db.query(Visit.id).filter(Visit.id == visit_id).first()
            if not exists:
                logger.warning(
                    "job.send_visit_reminder: visit %s not found", visit_id
                )
            else:
                logger.info(
                    "job.send_visit_reminder: visit %s already reminded "
                    "(claim lost), skipping",
                    visit_id,
                )
            return
        claimed = True

        # Phase 2 — dispatch OUTSIDE any transaction/lock. Crash-window
        # tradeoff (documented): if the worker dies after the claim commit
        # but before the provider call completes, the stamp stays set and
        # the reminder is lost (at-most-once). That is accepted over the
        # alternative — holding the visit row lock across external I/O for
        # up to the job timeout, blocking every concurrent write to the
        # same visit.
        service = NotificationService(db)
        result = await service.send_confirmation_reminder(db, visit_id, hours_before=24)

        if not result.get("success"):
            logger.warning(
                "job.send_visit_reminder: send failed for visit %s: %s",
                visit_id, result.get("error", "unknown"),
            )
            # Release the claim in the handler below — let arq retry.
            raise RuntimeError(f"Notification send failed: {result.get('error')}")

        # Phase 3 — the claim IS the stamp; nothing further to write.
        logger.info(
            "job.send_visit_reminder: visit %s reminded via %s",
            visit_id, result.get("channel", channel),
        )
    except Exception:
        # Rollback first — the failed service call may have left uncommitted
        # partial state on the session. Then release OUR claim so arq's
        # retry can re-deliver (at-least-once for in-process failures).
        db.rollback()
        if claimed:
            db.execute(
                update(Visit)
                .where(Visit.id == visit_id)
                .values(reminder_sent_at=None)
            )
            db.commit()
        logger.exception("job.send_visit_reminder failed for visit %s", visit_id)
        raise  # arq will retry per retry_policy
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

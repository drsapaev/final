"""Task scheduler — thin shim that enqueues jobs onto arq's Redis pool.

P2.3 → PR-1: uses real arq. Enqueue failures are FAIL-CLOSED: if arq is
missing or Redis is unreachable, ``TaskEnqueueError`` is raised — the
caller never receives a fake job ID that would read as "job successfully
enqueued" in production (Redis unavailability there is a P1 incident and
must surface, not be swallowed).

Pattern:
    from app.tasks import enqueue_reminder, run_data_retention

    await enqueue_reminder(visit_id=123)

Each task function is async and idempotent. The arq worker entry point is
`app.tasks.worker.WorkerSettings` — run with: `arq app.tasks.worker.WorkerSettings`.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)


class TaskEnqueueError(RuntimeError):
    """Raised when a task could NOT actually be enqueued onto Redis.

    Fail-closed contract (PR-1): producers must be able to trust that a
    returned job ID means the job exists on the 'clinic' queue. Missing
    arq, unreachable Redis, or any transport error raises instead of
    returning a phantom ID.
    """


async def _close_pool(pool: Any) -> None:
    """Close an arq pool across supported arq versions (aclose/close)."""
    close = getattr(pool, "aclose", None)
    if close is None:
        close = pool.close
    result = close()
    if result is not None:
        await result


async def _enqueue(func_name: str, **kwargs: Any) -> str:
    """Enqueue a job on arq's Redis pool. Returns job ID.

    Enqueues onto the SAME queue the worker consumes (QUEUE_NAME = 'clinic')
    — arq's default queue would silently strand the job.

    Raises:
        TaskEnqueueError: arq is not installed, Redis is unreachable, or
            the transport failed for any other reason. No fallback, no
            fake job ID.
    """
    job_id = kwargs.pop("_job_id", None) or f"{func_name}:{uuid4()}"

    try:
        from arq import create_pool

        from app.tasks.worker import QUEUE_NAME, _parse_redis_settings

        redis_settings = _parse_redis_settings(settings.ARQ_REDIS_URL)
        pool = await create_pool(redis_settings)
        try:
            job = await pool.enqueue_job(
                func_name, **kwargs, _job_id=job_id, _queue_name=QUEUE_NAME
            )
        finally:
            await _close_pool(pool)

        if job is None:
            # Job with this ID already enqueued — idempotent skip. Honest:
            # the job DOES exist on the queue, so returning the ID is true.
            logger.info("task.enqueue.skip_duplicate job_id=%s func=%s", job_id, func_name)
        else:
            logger.info("task.enqueue.ok job_id=%s func=%s queue=%s", job_id, func_name, QUEUE_NAME)
        return job_id

    except Exception as e:
        # arq missing (ImportError) or Redis unreachable/transport error.
        # FAIL-CLOSED (PR-1): a returned job ID must mean the job is really
        # on the queue. Log loudly and surface to the caller — silently
        # reporting success would strand the task with nobody the wiser.
        # NOTE: QUEUE_NAME is intentionally not referenced here — the
        # in-try import may itself be the failure (arq missing).
        logger.error(
            "task.enqueue.failed job_id=%s func=%s error=%s:%s",
            job_id, func_name, type(e).__name__, e,
        )
        raise TaskEnqueueError(
            f"Failed to enqueue {func_name!r} onto the 'clinic' queue "
            f"(app.tasks.worker.QUEUE_NAME): {type(e).__name__}: {e}"
        ) from e


# ---------------------------------------------------------------------------
# Public task API
# ---------------------------------------------------------------------------

def build_reminder_schedule_version(visit) -> str:
    """SSOT for the reminder schedule-version format (Codex rounds 5-7).

    The version covers the full schedule (date AND time) plus the visit's
    monotonic ``reminder_generation`` (bumped by every schedule-mutating
    path), so a version is IMMUTABLE and never repeats: a reschedule cycle
    A→B→A produces three distinct generations, and the A→B→A re-enqueue can
    never collide with the retained arq result of the original A job.

    Format: ``"{visit_date.isoformat()}T{visit_time or '-'}#{generation}"``.
    """
    return (
        f"{visit.visit_date.isoformat()}T"
        f"{visit.visit_time or '-'}#"
        f"{visit.reminder_generation or 0}"
    )


async def enqueue_reminder(
    visit_id: int,
    channel: str = "telegram",
    *,
    schedule_version: str,
) -> str:
    """Send a reminder N hours before a visit.

    Args:
        visit_id: Target visit.
        channel: 'telegram' | 'sms' | 'email'.
        schedule_version: REQUIRED — the visit's CURRENT schedule version
            (``build_reminder_schedule_version(visit)``). Versioning the
            job by the schedule generation is what makes the reminder
            pipeline safe (Codex rounds 4-7): arq retains a completed
            job's result for keep_result seconds, and a value-based or
            missing version either collides with that retained result
            (enqueue_job returns None → the reminder silently strands) or
            lets a stale queued job deliver for an obsolete schedule. The
            worker REJECTS jobs whose version no longer matches the visit
            (date, time and generation all bind).

    Returns: job_id.
    """
    return await _enqueue(
        "send_visit_reminder",
        visit_id=visit_id,
        channel=channel,
        schedule_version=schedule_version,
        _job_id=f"reminder:visit:{visit_id}:{schedule_version}:{channel}",
    )


async def enqueue_data_retention() -> str:
    """Run the daily data retention cleanup (see data_retention.run_scheduled_cleanup)."""
    return await _enqueue("run_data_retention", _job_id="retention:daily")


async def enqueue_scheduled_report(report_type: str, filters: dict[str, Any] | None = None) -> str:
    """Generate a scheduled report async (see reporting_service)."""
    return await _enqueue(
        "generate_scheduled_report",
        report_type=report_type,
        filters=filters or {},
    )

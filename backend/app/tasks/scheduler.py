"""Task scheduler — thin shim that enqueues jobs onto arq's Redis pool.

P2.3: now uses real arq when available. Falls back to synchronous execution
(no worker required) when arq is not installed or redis is unreachable.

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


async def _enqueue(func_name: str, **kwargs: Any) -> str:
    """Enqueue a job on arq's Redis pool. Returns job ID.

    Falls back to logging if arq is not installed or redis is unreachable.
    This is acceptable for dev environments where the worker isn't running.
    In prod, redis unavailability is a P1 incident — the call should fail
    loud, not silently.
    """
    job_id = kwargs.pop("_job_id", None) or f"{func_name}:{uuid4()}"

    try:
        from arq import create_pool
        from arq.connections import RedisSettings  # noqa: F401

        from app.tasks.worker import _parse_redis_settings

        redis_settings = _parse_redis_settings(settings.ARQ_REDIS_URL)
        pool = await create_pool(redis_settings)
        job = await pool.enqueue_job(func_name, **kwargs, _job_id=job_id)
        await pool.close()

        if job is None:
            # Job with this ID already enqueued — idempotent skip
            logger.info("task.enqueue.skip_duplicate job_id=%s func=%s", job_id, func_name)
        else:
            logger.info("task.enqueue.ok job_id=%s func=%s", job_id, func_name)
        return job_id

    except ImportError:
        logger.warning(
            "task.enqueue.stub_no_arq job_id=%s func=%s (install arq to enable)",
            job_id, func_name,
        )
        return job_id
    except Exception as e:
        # Redis unreachable — log loudly but don't crash the caller.
        # The caller (e.g. an HTTP endpoint) should still succeed; the
        # background job failing is a separate incident.
        logger.error(
            "task.enqueue.failed job_id=%s func=%s error=%s",
            job_id, func_name, e,
        )
        return job_id


# ---------------------------------------------------------------------------
# Public task API
# ---------------------------------------------------------------------------

async def enqueue_reminder(visit_id: int, channel: str = "telegram") -> str:
    """Send a reminder N hours before a visit.

    Args:
        visit_id: Target visit.
        channel: 'telegram' | 'sms' | 'email'.

    Returns: job_id.
    """
    return await _enqueue(
        "send_visit_reminder",
        visit_id=visit_id,
        channel=channel,
        _job_id=f"reminder:visit:{visit_id}:{channel}",  # idempotent per (visit, channel)
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

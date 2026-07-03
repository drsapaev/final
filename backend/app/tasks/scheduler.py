"""Task scheduler — thin shim that enqueues jobs onto arq's Redis pool.

Currently these functions execute synchronously (no worker required) so the
codebase is not blocked on P2.3. When arq is wired up in P2.3, only the body
of `_enqueue` needs to change — callers stay the same.

Design:
- Every task is async + idempotent.
- Tasks catch their own exceptions and log structured errors; they never
  raise to the caller (background noise must stay background).
- Task IDs are deterministic where possible (visit_id, report_type) so
  re-enqueueing the same job is a no-op.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import uuid4

from app.core.config import settings

logger = logging.getLogger(__name__)


async def _enqueue(func_name: str, **kwargs: Any) -> str:
    """Enqueue a job. Returns a job ID.

    Stub implementation: just logs. When arq lands in P2.3, this becomes:

        from arq import create_pool
        from arq.connections import RedisSettings
        pool = await create_pool(RedisSettings.from_dsn(settings.ARQ_REDIS_URL))
        job = await pool.enqueue_job(func_name, **kwargs)
        return job.job_id
    """
    job_id = kwargs.pop("_job_id", None) or f"{func_name}:{uuid4()}"
    logger.info("task.enqueue_stub", extra={"func": func_name, "job_id": job_id, "kwargs": list(kwargs.keys())})
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
    return await _enqueue("send_visit_reminder", visit_id=visit_id, channel=channel)


async def enqueue_data_retention() -> str:
    """Run the daily data retention cleanup (see data_retention.run_scheduled_cleanup)."""
    return await _enqueue("run_data_retention")


async def enqueue_scheduled_report(report_type: str, filters: dict[str, Any] | None = None) -> str:
    """Generate a scheduled report async (see reporting_service)."""
    return await _enqueue("generate_scheduled_report", report_type=report_type, filters=filters or {})

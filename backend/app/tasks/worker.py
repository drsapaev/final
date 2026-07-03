"""arq worker entry point. Stub — real wiring lands in P2.3.

Run with:
    arq app.tasks.worker.WorkerSettings

Once P2.3 is done, this file will:
- Import the actual task implementations (send_visit_reminder, etc.)
- Configure RedisSettings from settings.ARQ_REDIS_URL
- Set max_jobs, job_timeout, health_check_interval
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


async def startup(ctx):  # pragma: no cover
    logger.info("arq.worker.startup")


async def shutdown(ctx):  # pragma: no cover
    logger.info("arq.worker.shutdown")


# Will be populated in P2.3
functions: list = []


class WorkerSettings:  # pragma: no cover
    functions = functions
    on_startup = startup
    on_shutdown = shutdown
    # redis_settings — set in P2.3 from settings.ARQ_REDIS_URL
    max_jobs = 10
    job_timeout = 300
    health_check_interval = 30

"""
Live enqueue+process proof for the arq worker (runbook Check 5).

The staging smoke check proves worker module wiring only. This script
proves the actual pipeline: a job is ENQUEUED onto Redis and PROCESSED by
an in-process arq Worker, and the result is read back.

Safety:
- Uses a dedicated scratch queue (default `arq:smoke-check`), never the
  application's default queue, so a production worker consuming the app
  queue is never affected.
- Registers a single throwaway coroutine (`smoke_echo`); no business jobs
  (visit reminders, data retention) can run from this queue.
- Deletes its own scratch keys on exit.

Usage:
    cd backend && python -m app.scripts.arq_enqueue_process_check

    # explicit redis (default: $ARQ_TEST_REDIS_URL, then $REDIS_URL)
    cd backend && python -m app.scripts.arq_enqueue_process_check \
        --redis-url redis://localhost:6379/0

Exit codes:
    0 = job enqueued, processed, result verified
    1 = enqueue/process/result failed
    2 = skipped (no Redis URL configured or Redis unreachable)
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

DEFAULT_QUEUE = "arq:smoke-check"
DEFAULT_TIMEOUT = 30.0
PAYLOAD = "arq-smoke-ok"


def _scratch_keys(queue_name: str) -> list[str]:
    return [queue_name, f"{queue_name}:health-check", f"{queue_name}:stats"]


def resolve_redis_url(explicit: str | None) -> str | None:
    return (
        (explicit or "").strip()
        or (os.getenv("ARQ_TEST_REDIS_URL") or "").strip()
        or (os.getenv("REDIS_URL") or "").strip()
        or None
    )


async def run_check(redis_url: str, queue_name: str, timeout: float) -> tuple[int, str]:
    from arq import func
    from arq.connections import RedisSettings, create_pool
    from arq.worker import Worker
    # NOTE: explicit name — arq 0.26 registers nested coroutines by their
    # __qualname__ ("run_check.<locals>.smoke_echo"), which would never match
    # the enqueued function name. func(coroutine) alone would do that.
    async def _smoke_echo(ctx: dict[str, Any], value: str) -> str:
        return value

    smoke_echo = func(_smoke_echo, name="smoke_echo")

    pool = await create_pool(RedisSettings.from_dsn(redis_url))
    job_id: str | None = None
    try:
        job = await pool.enqueue_job("smoke_echo", PAYLOAD, _queue_name=queue_name)
        if job is None:
            return 1, "enqueue returned None (job id collision?)"
        job_id = job.job_id
        print(f"    enqueued job_id={job_id} queue={queue_name}")

        worker = Worker(
            functions=[smoke_echo],
            redis_pool=pool,
            queue_name=queue_name,
            burst=True,
            poll_delay=0.1,
            job_timeout=10,
            keep_result=10,
            handle_signals=False,
            max_jobs=1,
            log_results=False,
        )
        await worker.async_run()
        print("    burst worker finished")

        result = await asyncio.wait_for(job.result(timeout=timeout), timeout=timeout)
        if result != PAYLOAD:
            return 1, f"result mismatch: expected {PAYLOAD!r}, got {result!r}"
        print(f"    processed result={result!r}")
        return 0, "enqueue+process+result verified"
    finally:
        try:
            keys = _scratch_keys(queue_name) + ([job_id] if job_id else [])
            await pool.delete(*keys)
        except Exception:
            pass
        await pool.aclose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Live arq enqueue+process proof on a scratch queue (idempotent, self-cleaning)."
    )
    parser.add_argument("--redis-url", default=None, help="Redis DSN (default: $ARQ_TEST_REDIS_URL, then $REDIS_URL).")
    parser.add_argument("--queue", default=DEFAULT_QUEUE, help="Scratch queue name.")
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT, help="Seconds to wait for the job result.")
    args = parser.parse_args(argv)

    redis_url = resolve_redis_url(args.redis_url)
    if not redis_url:
        print("    arq enqueue+process check skipped: no ARQ_TEST_REDIS_URL / REDIS_URL configured")
        return 2

    try:
        code, message = asyncio.run(run_check(redis_url, args.queue, args.timeout))
    except Exception as exc:
        print(f"    arq enqueue+process check failed: {type(exc).__name__}: {exc}")
        return 1
    print(f"    {message}")
    return code


if __name__ == "__main__":
    sys.exit(main())

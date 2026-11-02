from __future__ import annotations

import asyncio
import threading

import pytest

from app.services.public_booking_request_notification_outbox import (
    OUTBOX_MAX_RETRY_SECONDS,
    retry_delay_seconds,
)


@pytest.mark.parametrize(
    ("attempt_count", "expected_seconds"),
    [
        (0, 60),
        (1, 60),
        (2, 120),
        (3, 240),
        (6, 1920),
        (8, OUTBOX_MAX_RETRY_SECONDS),
        (100, OUTBOX_MAX_RETRY_SECONDS),
    ],
)
def test_retry_delay_uses_capped_exponential_backoff(
    attempt_count: int, expected_seconds: int
) -> None:
    assert retry_delay_seconds(attempt_count) == expected_seconds


def test_notification_outbox_sweep_is_registered_as_worker_cron() -> None:
    pytest.importorskip("arq")
    from app.tasks.worker import (
        WorkerSettings,
        run_public_booking_request_notification_outbox,
    )

    assert run_public_booking_request_notification_outbox in WorkerSettings.functions
    assert any(
        getattr(job, "coroutine", None)
        is run_public_booking_request_notification_outbox
        for job in WorkerSettings.cron_jobs
    )


@pytest.mark.asyncio
async def test_notification_outbox_worker_keeps_event_loop_responsive(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("arq")
    from app.tasks import worker

    started = threading.Event()
    release = threading.Event()
    watchdog_fired = threading.Event()
    loop_ticked_while_batch_waited = False

    def blocking_batch(_database_url: str) -> dict[str, int]:
        started.set()
        if not release.wait(timeout=4):
            raise AssertionError("event loop failed to release the DB worker")
        return {"claimed": 0, "delivered": 0, "deferred": 0}

    def watchdog_release() -> None:
        watchdog_fired.set()
        release.set()

    watchdog = threading.Timer(2, watchdog_release)
    watchdog.start()
    monkeypatch.setattr(
        worker,
        "_process_public_booking_request_notification_outbox_batch",
        blocking_batch,
    )

    job = asyncio.create_task(worker.run_public_booking_request_notification_outbox({}))

    async def tick_event_loop() -> None:
        nonlocal loop_ticked_while_batch_waited
        assert await asyncio.to_thread(started.wait, 1)
        await asyncio.sleep(0)
        loop_ticked_while_batch_waited = not job.done()
        release.set()

    try:
        await asyncio.wait_for(asyncio.gather(job, tick_event_loop()), timeout=3)
    finally:
        watchdog.cancel()

    assert loop_ticked_while_batch_waited
    assert not watchdog_fired.is_set()

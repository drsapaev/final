from __future__ import annotations

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

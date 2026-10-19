from __future__ import annotations

import asyncio
import threading
from datetime import datetime, time, timedelta, timezone

import pytest

from app.services import public_site_media_cleanup as cleanup_module
from app.services.public_site_media_cleanup import PublicSiteMediaCleanupScheduler

TASHKENT = timezone(timedelta(hours=5))


def test_next_cleanup_at_uses_tashkent_daily_boundary() -> None:
    before = datetime(2026, 10, 19, 3, 59, tzinfo=TASHKENT)
    after = datetime(2026, 10, 19, 4, 1, tzinfo=TASHKENT)

    assert cleanup_module._next_cleanup_at(before, time(4, 0)) == datetime(
        2026, 10, 19, 4, 0, tzinfo=TASHKENT
    )
    assert cleanup_module._next_cleanup_at(after, time(4, 0)) == datetime(
        2026, 10, 20, 4, 0, tzinfo=TASHKENT
    )


@pytest.mark.asyncio
async def test_cleanup_runs_off_loop_and_scheduler_stops_cleanly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    main_thread_id = threading.get_ident()
    cleanup_thread_ids: list[int] = []
    completed = threading.Event()
    scheduler: PublicSiteMediaCleanupScheduler

    def cleanup() -> int:
        cleanup_thread_ids.append(threading.get_ident())
        scheduler.running = False
        completed.set()
        return 1

    monkeypatch.setattr(cleanup_module, "_seconds_until_next_cleanup", lambda *_: 0)
    scheduler = PublicSiteMediaCleanupScheduler(time(4, 0), cleanup=cleanup)
    await scheduler.start()

    try:
        assert await asyncio.wait_for(asyncio.to_thread(completed.wait, 5), timeout=6)
    finally:
        await scheduler.stop()

    assert cleanup_thread_ids
    assert cleanup_thread_ids[0] != main_thread_id
    assert scheduler.task is None
    assert not scheduler._inflight

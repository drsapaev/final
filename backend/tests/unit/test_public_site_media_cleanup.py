from __future__ import annotations

import os
import threading
from datetime import UTC, datetime, timedelta

import pytest

from app.services.public_site_media_service import PublicSiteMediaService


def _media_backup_name(suffix: str = "a1b2c3d4", extension: str = "jpg") -> str:
    return f"20200101T000000000000Z-{'a' * 64}-{suffix}.{extension}"


def test_cleanup_removes_only_expired_public_site_media_copies(tmp_path):
    backup_root = tmp_path / "public-site-media-backups"
    backup_root.mkdir()
    original_root = tmp_path / "public-site-media"
    original_root.mkdir()

    expired_copy = backup_root / _media_backup_name()
    expired_copy.write_bytes(b"expired-copy")
    fresh_copy = backup_root / _media_backup_name("b1b2c3d4", "png")
    fresh_copy.write_bytes(b"fresh-copy")
    database_backup = backup_root / "backup_manual_20200101_000000.db.gz"
    database_backup.write_bytes(b"database-backup")
    unrelated_file = backup_root / "readme.txt"
    unrelated_file.write_bytes(b"unrelated")
    original = original_root / ("a" * 64 + ".jpg")
    original.write_bytes(b"original")

    now = datetime(2026, 10, 19, 0, 0, tzinfo=UTC)
    old_timestamp = (now - timedelta(days=31)).timestamp()
    os.utime(expired_copy, (old_timestamp, old_timestamp))
    fresh_timestamp = (now - timedelta(days=1)).timestamp()
    os.utime(fresh_copy, (fresh_timestamp, fresh_timestamp))

    removed = PublicSiteMediaService.cleanup_expired_backups(
        backup_root=backup_root,
        retention_days=30,
        now=now,
    )

    assert removed == 1
    assert not expired_copy.exists()
    assert fresh_copy.read_bytes() == b"fresh-copy"
    assert database_backup.read_bytes() == b"database-backup"
    assert unrelated_file.read_bytes() == b"unrelated"
    assert original.read_bytes() == b"original"


def test_media_backup_cleanup_has_an_independent_daily_worker_schedule():
    pytest.importorskip("arq")
    from arq.cron import CronJob

    from app.tasks.worker import (
        WorkerSettings,
        run_public_site_media_backup_cleanup,
    )

    cron_jobs = [
        job
        for job in WorkerSettings.cron_jobs
        if isinstance(job, CronJob)
        and job.coroutine is run_public_site_media_backup_cleanup
    ]

    assert len(cron_jobs) == 1
    assert cron_jobs[0].hour == 4
    assert cron_jobs[0].minute == 0
    assert run_public_site_media_backup_cleanup in WorkerSettings.functions


@pytest.mark.asyncio
async def test_media_backup_cleanup_worker_runs_filesystem_work_off_event_loop(
    monkeypatch,
):
    pytest.importorskip("arq")
    from app.tasks.worker import run_public_site_media_backup_cleanup

    caller_thread = threading.get_ident()
    cleanup_threads: list[int] = []

    def cleanup() -> int:
        cleanup_threads.append(threading.get_ident())
        return 2

    monkeypatch.setattr(
        PublicSiteMediaService,
        "cleanup_expired_backups",
        staticmethod(cleanup),
    )

    result = await run_public_site_media_backup_cleanup({})

    assert result == 2
    assert cleanup_threads
    assert cleanup_threads[0] != caller_thread

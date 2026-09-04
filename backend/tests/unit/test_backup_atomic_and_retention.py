"""Backup hygiene regressions (Sentry P0s of 2026-08-28).

1. Retention cleanup must compare aware datetimes (naive fromtimestamp
   vs aware cutoff raised TypeError on EVERY backup, paging the owner).
2. A failed dump must not leave a zero-byte artifact: pg_dump targets
   `<name>.tmp`, final name is published atomically on success, tmp
   leftovers are removed on failure.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from app.services.backup_service import BackupService


def _svc(tmp_path: Path, retention_days: int = 7, max_backups: int = 10):
    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = retention_days
    svc.max_backups = max_backups
    return svc


def test_cleanup_survives_old_artifacts_with_aware_cutoff(tmp_path):
    import os

    old = tmp_path / "backup_manual_20200101_000000.db.gz"
    old.write_bytes(b"x" * 32)
    old_stamp = (datetime.now(UTC) - timedelta(days=30)).timestamp()
    os.utime(old, (old_stamp, old_stamp))
    fresh = tmp_path / "backup_manual_20990101_000000.db.gz"
    fresh.write_bytes(b"y" * 32)

    _svc(tmp_path)._cleanup_old_backups()

    assert not old.exists()  # older than retention → removed
    assert fresh.exists()


def test_failed_dump_leaves_no_zero_byte_artifact(tmp_path, monkeypatch):
    svc = _svc(tmp_path)

    class _BoomDB:
        pass

    svc.db = _BoomDB()

    # _get_database_url поднимает ValueError при отсутствии DATABASE_URL —
    # это и есть «упавший дамп» до записи любого байта.
    monkeypatch.setattr(
        "app.services.backup_service._get_database_url",
        lambda: (_ for _ in ()).throw(ValueError("boom")),
    )

    import pytest

    with pytest.raises(Exception):
        svc.create_backup("scheduled")

    assert list(tmp_path.glob("*.tmp")) == []
    assert list(tmp_path.glob("backup_*.db*")) == []

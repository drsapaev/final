from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

import pytest

from app.core.config import Settings
from app.services.public_site_media_service import (
    PublicSiteMediaError,
    PublicSiteMediaService,
)


def _backup_copy_name(day: str, digest: str, suffix: str) -> str:
    return f"{day}T000000000000Z-{digest}-{suffix}.jpg"


def test_production_media_storage_does_not_enable_database_backups(
    tmp_path: Path,
) -> None:
    settings = Settings(
        SECRET_KEY="s" * 64,
        ENV="production",
        TESTING=False,
        AUTO_BACKUP_ENABLED=False,
        PUBLIC_SITE_MEDIA_ROOT=tmp_path / "media",
        PUBLIC_SITE_MEDIA_BACKUP_ROOT=tmp_path / "media-backups",
    )

    assert settings.PUBLIC_SITE_MEDIA_ROOT == tmp_path / "media"
    assert settings.PUBLIC_SITE_MEDIA_BACKUP_ROOT == tmp_path / "media-backups"
    assert settings.AUTO_BACKUP_ENABLED is False


def test_cleanup_removes_only_expired_generated_backup_copies(
    tmp_path: Path,
) -> None:
    backup_root = tmp_path / "backups"
    media_root = tmp_path / "media"
    backup_root.mkdir()
    media_root.mkdir()
    now = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)

    expired = backup_root / _backup_copy_name("20260901", "a" * 64, "b" * 8)
    recent = backup_root / _backup_copy_name("20261001", "c" * 64, "d" * 8)
    non_backup = backup_root / "keep-me.txt"
    original = media_root / ("e" * 64 + ".jpg")
    for path in (expired, recent, non_backup, original):
        path.write_bytes(b"synthetic")

    os.utime(expired, (now.timestamp() - 31 * 86400,) * 2)
    os.utime(recent, (now.timestamp() - 29 * 86400,) * 2)
    os.utime(non_backup, (now.timestamp() - 90 * 86400,) * 2)

    removed = PublicSiteMediaService.cleanup_expired_backups(
        backup_root=backup_root,
        retention_days=30,
        now=now,
    )

    assert removed == 1
    assert not expired.exists()
    assert recent.exists()
    assert non_backup.exists()
    assert original.read_bytes() == b"synthetic"


def test_cleanup_keeps_backup_copy_at_retention_cutoff(tmp_path: Path) -> None:
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    now = datetime(2026, 10, 19, 4, 0, tzinfo=UTC)
    cutoff_copy = backup_root / _backup_copy_name("20260919", "f" * 64, "0" * 8)
    cutoff_copy.write_bytes(b"synthetic")
    os.utime(cutoff_copy, (now.timestamp() - 30 * 86400,) * 2)

    removed = PublicSiteMediaService.cleanup_expired_backups(
        backup_root=backup_root,
        retention_days=30,
        now=now,
    )

    assert removed == 0
    assert cutoff_copy.exists()


def test_cleanup_fails_when_backup_root_is_missing(tmp_path: Path) -> None:
    missing_root = tmp_path / "missing-backups"

    with pytest.raises(PublicSiteMediaError) as error:
        PublicSiteMediaService.cleanup_expired_backups(backup_root=missing_root)

    assert error.value.status_code == 503
    assert error.value.code == "public_media_storage_unavailable"


def test_cleanup_fails_when_backup_root_is_a_symlink(tmp_path: Path) -> None:
    target = tmp_path / "backups"
    target.mkdir()
    symlink = tmp_path / "backup-link"
    try:
        symlink.symlink_to(target, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("directory symlink creation is not available")

    with pytest.raises(PublicSiteMediaError) as error:
        PublicSiteMediaService.cleanup_expired_backups(backup_root=symlink)

    assert error.value.status_code == 503
    assert error.value.code == "public_media_storage_unavailable"

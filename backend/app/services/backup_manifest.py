"""Backup-success manifest reader for /health/detailed.

The scheduled backup task (ops/scripts/backup_local_to_r2.py) writes
``last_backup_report.json`` ONLY after the whole chain succeeded:
identity check -> pg_dump -> archive verification -> Fernet encryption ->
retention -> R2 upload with size+SHA-256 HeadObject verification.

``read_backup_check()`` turns that manifest into the ``checks.backup``
block: fresh + verified => ``ok``; manifest missing => ``none``;
too old => ``stale``; manifest without a completed R2 verification =>
``incomplete``; archive hash no longer matching the manifest =>
``hash_mismatch``. A stale/incomplete backup is NOT an API availability
failure and must never flip the endpoint's overall status.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

STALE_AFTER_HOURS = 26.0
MANIFEST_FILENAME = "last_backup_report.json"


def read_backup_check(
    backup_dir: Path,
    *,
    manifest_path: Path | None = None,
    now: float | None = None,
) -> dict[str, Any]:
    """Build the ``checks.backup`` payload from the success manifest.

    ``manifest_path`` defaults to ``backup_dir / MANIFEST_FILENAME``.
    ``now`` is injectable for tests. Never raises: any unexpected content
    degrades to ``{"status": "unknown"}``.
    """
    manifest_path = manifest_path or (backup_dir / MANIFEST_FILENAME)
    try:
        raw = manifest_path.read_text(encoding="utf-8")
        manifest = json.loads(raw)
        if not isinstance(manifest, dict):
            raise ValueError("manifest is not an object")
    except FileNotFoundError:
        # No manifest yet: either pre-manifest pipeline or every run since
        # the cutover failed — either way there is no proven-good backup.
        return {
            "status": "none",
            "note": "backup success manifest not found; report from the backup task is required",
        }
    except Exception as exc:
        return {"status": "unknown", "error": f"manifest unreadable: {exc}"[:100]}

    completed = str(manifest.get("completed_at_utc") or "")
    try:
        completed_dt = datetime.fromisoformat(completed)
        if completed_dt.tzinfo is None:
            completed_dt = completed_dt.replace(tzinfo=UTC)
        age_hours = round(
            ((now if now is not None else time.time()) - completed_dt.timestamp()) / 3600.0, 1
        )
    except Exception:
        return {"status": "unknown", "error": "manifest has no valid completed_at_utc"}

    base: dict[str, Any] = {
        "completed_at_utc": completed or None,
        "source": manifest.get("source"),
        "schema": manifest.get("schema"),
        "archive": manifest.get("archive"),
        "age_hours": age_hours,
    }

    if manifest.get("r2_verified") is not True:
        # The manifest is only ever written after R2 verification, so this
        # means a hand-edited/corrupt manifest — treat as unknown, loudly.
        return {**base, "status": "incomplete", "r2_verified": False}

    if age_hours > STALE_AFTER_HOURS:
        return {**base, "status": "stale", "r2_verified": True}

    archive_name = str(manifest.get("archive") or "")
    archive_path = backup_dir / archive_name
    if not archive_name or not archive_path.is_file():
        # A fresh manifest (<26h) without the local archive is unexpected
        # (retention keeps 14) — flag for investigation instead of silently
        # passing; the R2 copy is still the offsite source of truth.
        return {**base, "status": "archive_missing", "r2_verified": True}

    expected = str(manifest.get("sha256") or "")
    actual = hashlib.sha256(archive_path.read_bytes()).hexdigest()
    if expected and actual != expected:
        return {**base, "status": "hash_mismatch", "r2_verified": True}

    return {**base, "status": "ok", "r2_verified": True, "archive_local": True}

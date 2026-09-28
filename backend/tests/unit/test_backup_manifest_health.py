"""Unit tests for the backup success-manifest health check.

The scheduled task writes last_backup_report.json ONLY after the full
chain (dump -> archive verify -> encrypt -> R2 upload + SHA-256 check)
succeeded. read_backup_check() must reflect that: freshness alone is not
success, and a missing/stale/failed upload keeps the alarm active without
ever affecting API availability (the caller does not 503 on it).
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.services.backup_manifest import STALE_AFTER_HOURS, read_backup_check


def _write_manifest(backup_dir: Path, payload: bytes = b"x" * 32, **overrides) -> dict:
    now = datetime.now(timezone.utc)
    manifest = {
        "completed_at_utc": now.isoformat(),
        "source": "local",
        "schema": "public",
        "archive": "local_prod_schema_public_x.dump.enc",
        "size_bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "r2_verified": True,
        "r2_key": "daily/encrypted-public/local_prod_schema_public_x.dump.enc",
    }
    manifest.update(overrides)
    backup_dir.mkdir(parents=True, exist_ok=True)
    (backup_dir / "last_backup_report.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    return manifest


def _write_archive(backup_dir: Path, name: str, payload: bytes = b"x" * 32) -> None:
    (backup_dir / name).write_bytes(payload)


def test_fresh_verified_archive_is_ok(tmp_path: Path):
    _write_manifest(tmp_path)
    _write_archive(tmp_path, "local_prod_schema_public_x.dump.enc")
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "ok"
    assert check["r2_verified"] is True
    assert check["archive_local"] is True


def test_missing_manifest_is_none_not_ok(tmp_path: Path):
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "none"


def test_old_manifest_is_stale(tmp_path: Path):
    _write_manifest(
        tmp_path,
        completed_at_utc=(datetime.now(timezone.utc) - timedelta(hours=30)).isoformat(),
    )
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "stale"


def test_manifest_without_r2_verification_is_incomplete(tmp_path: Path):
    _write_manifest(tmp_path, r2_verified=False)
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "incomplete"


def test_hash_mismatch_detected(tmp_path: Path):
    manifest = _write_manifest(tmp_path)
    _write_archive(tmp_path, manifest["archive"], b"tampered-payload")
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "hash_mismatch"


def test_missing_local_archive_is_flagged(tmp_path: Path):
    # Fresh manifest but the archive file is gone — unexpected under the
    # 14-item retention; must not silently pass as ok.
    _write_manifest(tmp_path)
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "archive_missing"


def test_naive_completed_at_treated_as_utc(tmp_path: Path):
    _write_manifest(
        tmp_path, completed_at_utc=datetime.utcnow().isoformat().replace(" ", "T")
    )
    _write_archive(tmp_path, "local_prod_schema_public_x.dump.enc")
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "ok"


def test_corrupt_manifest_is_unknown(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    (tmp_path / "last_backup_report.json").write_text("{not json", encoding="utf-8")
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "unknown"


def test_stale_threshold_is_26_hours():
    assert STALE_AFTER_HOURS == 26.0


def test_age_is_in_hours_not_seconds(tmp_path: Path):
    """Regression: age must be HOURS. Injected `now` 25h after completion
    must be ok and 27h must be stale — with the age accidentally computed
    in seconds both would read as >26 'hours' and the boundary would never
    be distinguishable."""
    payload_ts = datetime(2026, 9, 20, 12, 0, 0, tzinfo=timezone.utc).timestamp()
    _write_manifest(
        tmp_path,
        completed_at_utc=datetime.fromtimestamp(payload_ts, tz=timezone.utc).isoformat(),
    )
    _write_archive(tmp_path, "local_prod_schema_public_x.dump.enc")
    ok_check = read_backup_check(tmp_path, now=payload_ts + 25 * 3600)
    stale_check = read_backup_check(tmp_path, now=payload_ts + 27 * 3600)
    assert ok_check["status"] == "ok", f"25h must be ok, age_hours={ok_check['age_hours']}"
    assert ok_check["age_hours"] == 25.0
    assert stale_check["status"] == "stale"
    assert stale_check["age_hours"] == 27.0


def test_real_sha256_roundtrip(tmp_path: Path):
    payload = bytes(range(256)) * 4
    _write_manifest(tmp_path, payload=payload)
    _write_archive(tmp_path, "local_prod_schema_public_x.dump.enc", payload)
    check = read_backup_check(tmp_path, now=time.time())
    assert check["status"] == "ok"

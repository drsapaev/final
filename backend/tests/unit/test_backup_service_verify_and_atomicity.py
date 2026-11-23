"""BackupService archive verification and atomicity guards (BR-019/020/021/022).

Repairs the service-side findings of the backup/restore source review
(``docs/audits/2026-11-05-backup-restore-source-review.md``, PR #3882):

- **BR-019:** ``verify_backup`` routed every ``.db[.gz]`` artifact into
  SQLite's ``integrity_check``, so PostgreSQL custom-format dumps
  (``pg_dump -F c``) were reported ``{"valid": false, "file is not a
  database"}`` — a misleading recovery-readiness verdict on the Admin
  verify endpoint. Verification now routes by archive magic:
  ``PGDMP`` → ``pg_restore --list`` (fail-closed on nonzero), SQLite magic
  → ``PRAGMA integrity_check``, anything else → invalid with an explicit
  unknown-format error (the historical ``valid: size > 0`` fallback is
  gone).
- **BR-020:** the Admin restore's ``pg_restore`` gains transactional
  semantics — ``--single-transaction --if-exists`` alongside ``-c`` — so a
  mid-restore failure no longer leaves partly committed DDL. The broader
  maintenance-gate/isolated-target protocol remains an operator policy
  decision tracked in the ledger.
- **BR-021:** retention cleanup's count-limit pass operates on the filtered
  survivor list instead of the pre-cleanup snapshot (no duplicate unlink,
  no misleading "Error cleaning up backups" log).
- **BR-022:** compression writes this operation's private ``.gz.tmp``,
  validates it, atomically publishes, and removes only its own temp file —
  a failed compression can no longer leave a partial published-looking
  ``.db.gz``.

No real database, no real PostgreSQL subprocess, no real backup material:
synthetic files in pytest temporary directories only.
"""

from __future__ import annotations

import gzip
import io
import os
import sqlite3
import subprocess
from pathlib import Path

import pytest

from app.services import backup_service as backup_service_module  # noqa: E402
from app.services.backup_service import BackupService  # noqa: E402


def _ok(cmd, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(cmd, 0, stdout, "")


def _make_service(tmp_path: Path) -> BackupService:
    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 10
    svc.db = None
    return svc


def _gzip_bytes(payload: bytes) -> bytes:
    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(payload)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# BR-019 — format-aware verify_backup
# ---------------------------------------------------------------------------


def test_verify_routes_sqlite_archive_to_integrity_check(tmp_path):
    """BR-019 keeper: a real SQLite archive keeps the PRAGMA path."""
    svc = _make_service(tmp_path)
    archive = tmp_path / "backup_manual_20260101_120000.db"
    conn = sqlite3.connect(archive)
    conn.execute("CREATE TABLE synthetic_probe (id INTEGER PRIMARY KEY, note TEXT)")
    conn.execute("INSERT INTO synthetic_probe (note) VALUES ('synthetic')")
    conn.commit()
    conn.close()

    result = svc.verify_backup(archive.name)

    assert result["valid"] is True, result
    assert result["format"] == "sqlite"
    assert "integrity_check" in result["verify_mode"]


def test_verify_routes_pg_custom_dump_to_pg_restore_list(tmp_path, monkeypatch):
    """BR-019: a PostgreSQL custom-format dump under a .db name must be
    verified via pg_restore --list, not dismissed as an invalid SQLite file."""
    svc = _make_service(tmp_path)
    archive = tmp_path / "backup_manual_20260101_130000.db"
    archive.write_bytes(b"PGDMP" + b"\x00" * 32)  # synthetic custom-format magic

    monkeypatch.setattr(
        backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}"
    )
    recorded: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        recorded.append([str(part) for part in cmd])
        return _ok(cmd, stdout=" synthetic archive TOC line\n")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_run)

    result = svc.verify_backup(archive.name)

    assert result["valid"] is True, result
    assert result["format"] == "postgresql-custom"
    assert "pg_restore --list" in result["verify_mode"]
    assert recorded and any(
        "-l" in cmd for cmd in recorded
    ), "pg_restore --list must be the verification tool"


def test_verify_routes_pg_custom_gz_archive_via_private_extraction(
    tmp_path, monkeypatch
):
    """BR-019: a gzip-wrapped PostgreSQL dump must be verified after private
    extraction, and no temp file may leak."""
    svc = _make_service(tmp_path)
    archive = tmp_path / "backup_manual_20260101_140000.db.gz"
    archive.write_bytes(_gzip_bytes(b"PGDMP" + b"\x00" * 32))

    monkeypatch.setattr(
        backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}"
    )
    monkeypatch.setattr(
        backup_service_module.subprocess,
        "run",
        lambda cmd, **kw: _ok(cmd, stdout="TOC\n"),
    )

    result = svc.verify_backup(archive.name)

    assert result["valid"] is True, result
    assert result["format"] == "postgresql-custom"
    leftovers = [p.name for p in tmp_path.iterdir() if p.suffix == ".db"]
    assert leftovers == [], f"extraction temp leaked: {leftovers}"


def test_verify_fails_closed_on_unknown_archive_content(tmp_path, monkeypatch):
    """BR-019: unreadable bytes under a backup name are invalid with an
    explicit unknown-format error — never the historical ``valid: size > 0``."""
    svc = _make_service(tmp_path)
    archive = tmp_path / "backup_manual_20260101_150000.db"
    archive.write_bytes(b"NOT-AN-ARCHIVE-HEADER-AT-ALL")

    monkeypatch.setattr(backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}")
    monkeypatch.setattr(
        backup_service_module.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, "", "pg_restore: not a PostgreSQL archive"),
    )

    result = svc.verify_backup(archive.name)

    assert result["valid"] is False, result
    assert "unknown archive format" in result.get("error", ""), result


def test_verify_fails_closed_when_pg_restore_list_fails(tmp_path, monkeypatch):
    """BR-019: a corrupted custom archive (pg_restore --list nonzero) must
    produce an explicit failure."""
    svc = _make_service(tmp_path)
    archive = tmp_path / "backup_manual_20260101_160000.db"
    archive.write_bytes(b"PGDMP" + b"\xff" * 8)  # truncated/corrupt body

    monkeypatch.setattr(
        backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}"
    )
    monkeypatch.setattr(
        backup_service_module.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 1, "", "pg_restore: synthetic corruption"
        ),
    )

    result = svc.verify_backup(archive.name)

    assert result["valid"] is False, result
    assert "pg_restore --list failed" in result.get("error", ""), result


# ---------------------------------------------------------------------------
# BR-020 — transactional Admin restore
# ---------------------------------------------------------------------------


def test_restore_backup_pins_single_transaction(tmp_path, monkeypatch):
    """BR-020: the Admin PostgreSQL restore must run
    ``pg_restore -c --if-exists --single-transaction`` so a failed restore
    does not leave partly committed DDL against the active database."""
    svc = _make_service(tmp_path)
    archive = tmp_path / "backup_manual_20260101_170000.db"
    archive.write_bytes(b"PGDMP-SYNTHETIC")

    monkeypatch.setattr(
        backup_service_module,
        "_get_database_url",
        lambda: "postgresql://restore_user:restore_pwd@localhost:5432/clinic",
    )
    monkeypatch.setattr(
        backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}"
    )
    monkeypatch.setattr(
        svc, "create_backup", lambda backup_type: {"filename": "safety.db"}
    )

    recorded: list[list[str]] = []

    def fake_run(cmd, env=None, capture_output=True, text=True, check=False):
        recorded.append([str(part) for part in cmd])
        return _ok(cmd)

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_run)

    result = svc.restore_backup(archive.name)

    assert result["success"] is True, result
    pg_cmd = next(cmd for cmd in recorded if "pg_restore" in cmd[0])
    assert (
        "--single-transaction" in pg_cmd
    ), f"Admin restore must be transactional (--single-transaction); got: {pg_cmd}"
    assert (
        "-c" in pg_cmd and "--if-exists" in pg_cmd
    ), f"clean-if-exists semantics lost: {pg_cmd}"


def test_restore_backup_reports_failure_without_success_verdict(tmp_path, monkeypatch):
    """BR-020 keeper: a nonzero pg_restore status must still abort the
    restore with an exception — no success dict may be returned."""
    svc = _make_service(tmp_path)
    archive = tmp_path / "backup_manual_20260101_180000.db"
    archive.write_bytes(b"PGDMP-SYNTHETIC")

    monkeypatch.setattr(
        backup_service_module,
        "_get_database_url",
        lambda: "postgresql://restore_user:restore_pwd@localhost:5432/clinic",
    )
    monkeypatch.setattr(
        backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}"
    )
    monkeypatch.setattr(
        svc, "create_backup", lambda backup_type: {"filename": "safety.db"}
    )
    monkeypatch.setattr(
        backup_service_module.subprocess,
        "run",
        lambda cmd, **kw: subprocess.CompletedProcess(
            cmd, 1, "", "pg_restore: synthetic failure"
        ),
    )

    with pytest.raises(Exception, match="pg_restore failed"):
        svc.restore_backup(archive.name)


# ---------------------------------------------------------------------------
# BR-021 — retention cleanup filtered survivor list
# ---------------------------------------------------------------------------


def test_retention_cleanup_uses_filtered_survivor_list(tmp_path, caplog):
    """BR-021: with one expired and two fresh archives and max_backups=1,
    cleanup must remove the expired file and the oldest survivor exactly
    once each — no duplicate unlink, no misleading error log."""
    svc = _make_service(tmp_path)
    svc.max_backups = 1

    expired = tmp_path / "backup_manual_20200101_000000.db"
    survivor_old = tmp_path / "backup_manual_20990101_000000.db"
    survivor_new = tmp_path / "backup_manual_20990101_010000.db"
    for path, mtime in (
        (expired, 1_577_836_800),  # 2020-01-01 — well past the 7-day cutoff
        (survivor_old, 4_102_444_800),  # 2099-12-31, older of the two fresh
        (survivor_new, 4_102_448_400),  # 2099-12-31, newest
    ):
        path.write_bytes(b"SYNTHETIC-ARCHIVE")
        os.utime(path, (mtime, mtime))

    import logging

    with caplog.at_level(logging.ERROR):
        svc._cleanup_old_backups()

    assert not expired.exists(), "expired archive must be removed"
    assert survivor_new.exists(), "the newest archive must survive"
    assert not survivor_old.exists(), "the excess survivor must be removed"
    retention_errors = [
        rec.getMessage()
        for rec in caplog.records
        if "Error cleaning up backups" in rec.getMessage()
    ]
    assert (
        retention_errors == []
    ), f"duplicate unlink produced a misleading retention error: {retention_errors}"


# ---------------------------------------------------------------------------
# BR-022 — atomic compression with own-temp cleanup
# ---------------------------------------------------------------------------


def test_compress_success_publishes_complete_gz(tmp_path):
    """BR-022 keeper: a successful compression publishes a complete archive
    and leaves no temp file behind."""
    svc = _make_service(tmp_path)
    source = tmp_path / "backup_manual_20260101_190000.db"
    source.write_bytes(b"SYNTHETIC-DUMP-CONTENT" * 64)

    result = svc._compress_backup(source)

    assert result is not None and result.exists()
    with gzip.open(result, "rb") as f_in:
        assert f_in.read() == source.read_bytes() == b"SYNTHETIC-DUMP-CONTENT" * 64
    assert not list(tmp_path.glob("*.tmp")), "temp file leaked"


def test_compress_failure_leaves_no_partial_gz(tmp_path, monkeypatch):
    """BR-022: a mid-write compression failure must leave no partial
    published ``.db.gz`` and no temp file — the good uncompressed source
    stays intact."""
    svc = _make_service(tmp_path)
    source = tmp_path / "backup_manual_20260101_200000.db"
    source.write_bytes(b"SYNTHETIC-DUMP-CONTENT" * 64)

    def failing_copyfileobj(*_args, **_kwargs):
        raise OSError("synthetic: disk full mid-compression")

    monkeypatch.setattr(
        backup_service_module.shutil, "copyfileobj", failing_copyfileobj
    )

    result = svc._compress_backup(source)

    assert result is None
    assert (
        source.exists() and source.read_bytes() == b"SYNTHETIC-DUMP-CONTENT" * 64
    ), "the good uncompressed source must survive a failed compression"
    partial_gz = list(tmp_path.glob("*.db.gz"))
    assert (
        partial_gz == []
    ), f"a partial published-looking archive remained: {partial_gz}"
    assert not list(tmp_path.glob("*.tmp")), "this run's temp file was not removed"


def test_compress_refuses_to_clobber_existing_archive(tmp_path):
    """BR-022 keeper: an existing archive at the target name must never be
    overwritten by compression."""
    svc = _make_service(tmp_path)
    source = tmp_path / "backup_manual_20260101_210000.db"
    source.write_bytes(b"SOURCE-CONTENT")
    existing_gz = tmp_path / "backup_manual_20260101_210000.db.gz"
    existing_gz.write_bytes(b"PRE-EXISTING-SENTINEL")

    result = svc._compress_backup(source)

    assert result is None
    assert (
        existing_gz.read_bytes() == b"PRE-EXISTING-SENTINEL"
    ), "compression clobbered an existing archive"

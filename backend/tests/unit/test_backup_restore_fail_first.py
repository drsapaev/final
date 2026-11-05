"""Fail-first regression drafts for backup/restore findings BR-008/012/013/016/017/018.

Derived from ``docs/audits/2026-11-05-backup-restore-source-review.md``
(Pull Request #3882). Every PostgreSQL subprocess command is mocked in this
module: no real ``DROP DATABASE``, ``CREATE DATABASE``, ``pg_restore`` or
``psql`` is ever executed, no real database is contacted, and no real backup
material is used — only synthetic files in pytest temporary directories.

Against the reviewed source these tests are EXPECTED TO FAIL for the intended
reason (the current implementation exhibits the finding). After the narrow
fail-closed fixes land in separate gated fix PRs, each test must turn green.

Coverage:
- BR-012  dr_drill must refuse a target DB name equal to the source DB name
          before issuing any destructive command.
- BR-013  dr_drill must fail on a nonzero pg_restore exit status even when
          stderr contains no ``ERROR:`` token.
- BR-016  dr_drill gzip extraction must not overwrite an adjacent same-stem
          archive in the backup directory.
- BR-017  dr_drill cleanup must not drop a database this run did not create
          (``DRILL_DB_DROP_ON_START=0`` with a failed ``CREATE``).
- BR-008  run_update_rehearsal readiness timeout must be handled by the
          rollback supervisor (currently ``SystemExit`` escapes ``except
          Exception`` and rollback is skipped).
- BR-018  BackupService failure cleanup must remove only its own temp file,
          never another writer's in-flight ``*.tmp``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
OPS_SCRIPTS = REPO_ROOT / "ops" / "vps" / "scripts"
if str(OPS_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(OPS_SCRIPTS))

import app.scripts.dr_drill as dr_drill  # noqa: E402
import run_update_rehearsal as rur  # noqa: E402
from app.services.backup_service import BackupService  # noqa: E402
from app.services import backup_service as backup_service_module  # noqa: E402
from clinic_lifecycle_common import LifecycleError  # noqa: E402


def _ok(cmd, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(cmd, 0, stdout, "")


def _drill_env(monkeypatch, *, drill_db_name: str, drop_on_start: bool):
    """Common drill monkeypatching: no pg tools check, synthetic source."""
    monkeypatch.setattr(dr_drill, "DRILL_DB_NAME", drill_db_name)
    monkeypatch.setattr(dr_drill, "DRILL_DB_DROP_ON_START", drop_on_start)
    monkeypatch.setattr(dr_drill, "ensure_pg_tools", lambda: None)
    monkeypatch.setattr(
        dr_drill, "parse_source_db_url",
        lambda: ("drill_user", "drill_pass", "drill_host.invalid", 5432, "clinicdb_src"),
    )


# ---------------------------------------------------------------------------
# BR-012 — source/target DB identity collision must fail closed
# ---------------------------------------------------------------------------


def test_dr_drill_refuses_target_db_equal_to_source_db(tmp_path, monkeypatch):
    """BR-012: with DRILL_DB_NAME equal to the source database name the drill
    must exit nonzero BEFORE any ``DROP DATABASE`` is issued."""
    backup = tmp_path / "synthetic.dump"
    backup.write_bytes(b"SYNTHETIC-ARCHIVE")

    issued: list[list[str]] = []

    def fake_run(cmd, env=None, check=True):
        issued.append([str(part) for part in cmd])
        # smoke queries return plausible row counts
        return _ok(cmd, stdout="3\n")

    monkeypatch.setattr(dr_drill, "_run", fake_run)
    monkeypatch.setattr(dr_drill, "find_latest_backup", lambda: backup)
    _drill_env(monkeypatch, drill_db_name="clinicdb_src", drop_on_start=True)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code != 0, "drill must refuse a same-name target"
    joined = [" ".join(cmd) for cmd in issued]
    assert not any("DROP DATABASE" in cmd for cmd in joined), (
        "drill issued a DROP DATABASE although the target equals the source DB "
        f"(commands: {joined})"
    )


# ---------------------------------------------------------------------------
# BR-013 — nonzero pg_restore status must fail the drill
# ---------------------------------------------------------------------------


def test_dr_drill_fails_on_pg_restore_nonzero_without_error_line(tmp_path, monkeypatch):
    """BR-013: ``pg_restore`` returning 1 with diagnostics that contain no
    ``ERROR:`` token must abort the drill with a nonzero exit status."""
    backup = tmp_path / "synthetic.dump"
    backup.write_bytes(b"SYNTHETIC-ARCHIVE")

    def fake_run(cmd, env=None, check=True):
        if cmd[0] == "pg_restore":
            return subprocess.CompletedProcess(
                cmd, 1, "", "pg_restore: connection interrupted\n"
            )
        return _ok(cmd, stdout="3\n")

    monkeypatch.setattr(dr_drill, "_run", fake_run)
    monkeypatch.setattr(dr_drill, "find_latest_backup", lambda: backup)
    _drill_env(monkeypatch, drill_db_name="clinic_dr_drill", drop_on_start=True)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code != 0, (
        "drill must treat a nonzero pg_restore status as failure even without "
        "an ERROR: line in stderr"
    )


# ---------------------------------------------------------------------------
# BR-016 — gzip extraction must not clobber an adjacent archive
# ---------------------------------------------------------------------------


def test_dr_drill_gzip_extraction_preserves_adjacent_dump(tmp_path, monkeypatch):
    """BR-016: extracting ``synthetic.dump.gz`` must never truncate the
    pre-existing adjacent ``synthetic.dump`` in the same directory."""
    sentinel = tmp_path / "synthetic.dump"
    sentinel.write_bytes(b"ORIGINAL-SENTINEL-BYTES")
    compressed = tmp_path / "synthetic.dump.gz"
    compressed.write_bytes(_gzip_bytes(b"DECOMPRESSED-CONTENT"))

    monkeypatch.setattr(
        dr_drill, "_run",
        lambda cmd, env=None, check=True: _ok(cmd),
    )
    monkeypatch.setattr(dr_drill, "ensure_pg_tools", lambda: None)

    dr_drill.restore_backup(compressed, "drill_user", "drill_pass", "drill_host.invalid", 5432)

    assert sentinel.read_bytes() == b"ORIGINAL-SENTINEL-BYTES", (
        "gzip extraction overwrote the adjacent same-stem archive"
    )


def _gzip_bytes(payload: bytes) -> bytes:
    import io
    import gzip

    buf = io.BytesIO()
    with gzip.GzipFile(fileobj=buf, mode="wb") as gz:
        gz.write(payload)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# BR-017 — cleanup must not drop a database this run did not create
# ---------------------------------------------------------------------------


def test_dr_drill_no_destructive_cleanup_when_create_failed(tmp_path, monkeypatch):
    """BR-017: with ``DRILL_DB_DROP_ON_START=0`` and a failed ``CREATE
    DATABASE`` for a preexisting target, the drill must not later DROP that
    preexisting database."""
    backup = tmp_path / "synthetic.dump"
    backup.write_bytes(b"SYNTHETIC-ARCHIVE")

    issued: list[list[str]] = []

    def fake_run(cmd, env=None, check=True):
        parts = [str(part) for part in cmd]
        issued.append(parts)
        if any("CREATE DATABASE" in part for part in parts):
            return subprocess.CompletedProcess(
                cmd, 1, "", 'ERROR: database "preexisting_target" already exists\n'
            )
        return _ok(cmd, stdout="3\n")

    monkeypatch.setattr(dr_drill, "_run", fake_run)
    monkeypatch.setattr(dr_drill, "find_latest_backup", lambda: backup)
    _drill_env(monkeypatch, drill_db_name="preexisting_target", drop_on_start=False)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    joined = [" ".join(cmd) for cmd in issued]
    drop_issued = [cmd for cmd in joined if "DROP DATABASE" in cmd]
    assert not drop_issued, (
        "drill cleanup dropped a database this run did not create "
        f"(commands: {drop_issued})"
    )
    assert excinfo.value.code != 0, (
        "drill must fail closed when the scratch target cannot be provisioned"
    )


# ---------------------------------------------------------------------------
# BR-008 — readiness timeout must be handled by the rollback supervisor
# ---------------------------------------------------------------------------


def test_update_rehearsal_rolls_back_on_backend_readiness_timeout(monkeypatch):
    """BR-008: when the backend never becomes ready after deploy+migrations,
    the supervisor must invoke ``rollback_release.py`` (bounded, handled
    failure) instead of letting ``SystemExit`` escape ``except Exception``."""
    invoked: list[str] = []

    def fake_invoke(script_name, *, extra_env=None):
        invoked.append(script_name)
        if script_name == "backup_db.py":
            return "BACKUP_FILE=/tmp/synthetic-backup.dump\n"
        return ""

    calls = {"n": 0}

    def fake_monotonic() -> float:
        calls["n"] += 1
        return 100.0 * calls["n"]

    monkeypatch.setattr(rur, "_invoke", fake_invoke)

    def unreachable(*_args, **_kwargs):
        raise LifecycleError("synthetic: backend never reachable")

    monkeypatch.setattr(rur, "http_json", unreachable)
    monkeypatch.setattr(rur.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(rur.time, "sleep", lambda _s: None)
    monkeypatch.setenv("UPDATE_RELEASE_REF", "synthetic-release")

    with pytest.raises(SystemExit) as excinfo:
        rur.main()

    assert excinfo.value.code != 0, "readiness timeout must exit nonzero"
    assert "rollback_release.py" in invoked, (
        "readiness timeout bypassed the rollback handler: SystemExit escaped "
        f"except Exception; scripts invoked: {invoked}"
    )


# ---------------------------------------------------------------------------
# BR-018 — failed backup cleanup must spare other writers' temp files
# ---------------------------------------------------------------------------


def test_failed_backup_cleanup_preserves_other_writers_temp(tmp_path, monkeypatch):
    """BR-018: when backup A fails, its cleanup may remove only A's own temp
    file — not every ``*.tmp`` in the shared backup directory."""
    other = tmp_path / "backup_scheduled_20990101_999999.db.tmp"
    other.write_bytes(b"OTHER-WRITER-IN-FLIGHT")
    own = tmp_path / "backup_manual_20990101_000001.db.tmp"
    own.write_bytes(b"CURRENT-WRITER-LEFTOVER")

    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 10
    svc.db = None

    def boom() -> str:
        raise ValueError("synthetic failing dump")

    monkeypatch.setattr(backup_service_module, "_get_database_url", boom)

    with pytest.raises(Exception):
        svc.create_backup("manual")

    assert own.exists() is False, "the failed writer must remove its own temp file"
    assert other.exists(), "cleanup deleted another writer's in-flight temp file"
    assert other.read_bytes() == b"OTHER-WRITER-IN-FLIGHT", (
        "cleanup corrupted another writer's in-flight temp file"
    )

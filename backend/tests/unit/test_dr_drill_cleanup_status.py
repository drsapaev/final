"""DR drill cleanup status must be checked, verified and reported (BR-015).

Repairs BR-015 of the backup/restore source review
(``docs/audits/2026-11-05-backup-restore-source-review.md``, PR #3882):
the historical cleanup dropped the scratch database with ``psql``
``check=False`` and never verified the result, so a failed DROP left the
restored database — potentially holding confidential backup content — on
the server while the drill still exited 0 ("DR drill PASSED").

After the fix the cleanup DROP is checked (``-v ON_ERROR_STOP=1``), its
effect is verified against ``pg_database``, and a failed cleanup overrides
the process verdict with exit code 3 ("passed but leftover database needs
operator removal"). ``DRILL_KEEP_DB=1`` stays the explicit retain opt-out.

Every PostgreSQL subprocess is mocked: no real database is contacted, no
real ``DROP DATABASE`` is issued, no real backup material is used.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]

import app.scripts.dr_drill as dr_drill  # noqa: E402


def _ok(cmd, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(cmd, 0, stdout, "")


def _fail(cmd, stderr: str = "synthetic failure") -> subprocess.CalledProcessError:
    return subprocess.CalledProcessError(1, cmd, stderr=stderr)


@pytest.fixture()
def drill_env(monkeypatch, tmp_path):
    """Isolated drill environment: no pg tools check, synthetic source DB."""
    backup = tmp_path / "synthetic.dump"
    backup.write_bytes(b"SYNTHETIC-ARCHIVE")
    monkeypatch.setattr(dr_drill, "DRILL_DB_NAME", "synthetic_drill_target")
    monkeypatch.setattr(dr_drill, "DRILL_DB_DROP_ON_START", False)
    monkeypatch.setattr(dr_drill, "ensure_pg_tools", lambda: None)
    monkeypatch.setattr(
        dr_drill,
        "parse_source_db_url",
        lambda: (
            "drill_user",
            "drill_pass",
            "drill_host.invalid",
            5432,
            "clinicdb_src",
        ),
    )
    monkeypatch.setattr(dr_drill, "find_latest_backup", lambda: backup)
    monkeypatch.delenv("DRILL_KEEP_DB", raising=False)
    return tmp_path


def _install_run(monkeypatch, *, drop_result="ok", verify_stdout: str = ""):
    """Fake _run distinguishing smoke queries, cleanup DROP and verification."""
    commands: list[list[str]] = []

    def fake_run(cmd, env=None, check=True):
        parts = [str(part) for part in cmd]
        commands.append(parts)
        joined = " ".join(parts)
        if "pg_database" in joined:
            return _ok(cmd, stdout=verify_stdout)
        if "DROP DATABASE" in joined and "-d postgres" in joined:
            if drop_result == "fail":
                if check:
                    raise _fail(cmd)
            return _ok(cmd)
        if "CREATE DATABASE" in joined:
            return _ok(cmd)
        if cmd[0] == "pg_restore":
            return _ok(cmd)
        # smoke queries against the drill DB
        return _ok(cmd, stdout="3\n")

    monkeypatch.setattr(dr_drill, "_run", fake_run)
    return commands


def test_drill_exit_3_when_cleanup_drop_fails(drill_env, monkeypatch, caplog):
    """BR-015: a failed cleanup DROP must override the PASSED verdict with
    an explicit leftover-database exit status."""
    _install_run(monkeypatch, drop_result="fail")

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert (
        excinfo.value.code == 3
    ), f"failed cleanup must exit 3 (leftover DB), got {excinfo.value.code}"
    assert any(
        "LEFTOVER DATABASE" in rec.getMessage() for rec in caplog.records
    ), "the operator-visible leftover-database signal is missing"


def test_drill_exit_3_when_database_still_exists_after_drop(drill_env, monkeypatch):
    """BR-015: the cleanup must verify the database is actually gone — a
    silently failed DROP (exit 0, DB still listed) must not certify a clean
    server."""
    _install_run(monkeypatch, drop_result="ok", verify_stdout="1\n")

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert (
        excinfo.value.code == 3
    ), f"database still listed after DROP must exit 3, got {excinfo.value.code}"


def test_drill_cleanup_issues_checked_drop_with_on_error_stop(drill_env, monkeypatch):
    """BR-015 keeper: the cleanup DROP must carry ``ON_ERROR_STOP=1`` and run
    checked, so a SQL failure cannot vanish into a zero exit status."""
    commands = _install_run(monkeypatch, drop_result="ok", verify_stdout="")

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()
    assert excinfo.value.code == 0

    drop_cmds = [
        " ".join(cmd) for cmd in commands if any("DROP DATABASE" in p for p in cmd)
    ]
    assert drop_cmds, "cleanup must issue exactly the documented DROP"
    assert all(
        "ON_ERROR_STOP=1" in cmd for cmd in drop_cmds
    ), f"cleanup DROP must pin ON_ERROR_STOP=1: {drop_cmds}"


def test_drill_keep_db_preserves_scratch_without_drop(drill_env, monkeypatch):
    """BR-015 keeper: DRILL_KEEP_DB=1 must remain an explicit, clearly logged
    retain opt-out — no DROP may be issued."""
    monkeypatch.setenv("DRILL_KEEP_DB", "1")
    commands = _install_run(monkeypatch, drop_result="ok", verify_stdout="")

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()
    assert excinfo.value.code == 0

    assert not any(
        "DROP DATABASE" in " ".join(cmd) for cmd in commands
    ), "DRILL_KEEP_DB=1 must preserve the scratch database without a DROP"


def test_drill_success_path_still_exit_zero(drill_env, monkeypatch, caplog):
    """BR-015 keeper: a verified clean cleanup keeps the honest PASSED
    verdict (no overreach to nonzero)."""
    _install_run(monkeypatch, drop_result="ok", verify_stdout="")

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()
    assert excinfo.value.code == 0
    assert any("DR drill PASSED" in rec.getMessage() for rec in caplog.records)

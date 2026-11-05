"""Fail-closed guards for the VPS ``restore_db.py`` lifecycle script.

Repairs BR-001 and BR-007 of the backup/restore source review
(``docs/audits/2026-11-05-backup-restore-source-review.md``, PR #3882):

- **BR-001 (P1):** ``psql -f <archive>`` ran without ``ON_ERROR_STOP``,
  so psql kept executing statements after a SQL error and could exit 0
  — the wrapper then printed a success marker for an incomplete
  restore. The psql invocation now pins ``-X -v ON_ERROR_STOP=1``.
  The custom-format ``pg_restore`` branch is deliberately untouched
  (that transactional improvement is BR-011, a separate gated fix).
- **BR-007 (P2):** the ``.gz`` expansion helper created its plaintext
  temp file BEFORE the ``try/finally`` in ``main()``, so a malformed
  archive left an unencrypted SQL dump behind in the OS temp
  directory. Decompression now owns its cleanup, and the helper call
  lives inside the guarded block.

The tests import the REAL script and need no PostgreSQL: the psql
wiring is asserted through a recorded fake executable, the gzip
failure path through a truncated synthetic archive.
"""

from __future__ import annotations

import gzip
import importlib.util
import os
import stat
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
OPS_SCRIPTS = REPO_ROOT / "ops" / "vps" / "scripts"


def _load_script(name: str):
    """Import an ops lifecycle script by file path (sibling imports work)."""

    if str(OPS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(OPS_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        f"vps_lifecycle_{name}", OPS_SCRIPTS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def restore_env(tmp_path, monkeypatch):
    """Isolated lifecycle environment: no repo .env files, no live targets."""

    app_root = tmp_path / "repo"
    (app_root / "backend").mkdir(parents=True)
    monkeypatch.setenv("APP_ROOT", str(app_root))
    # BR-001/007 tests restore a synthetic target; the confirmation flag
    # mirrors an explicit operator decision, never a live DATABASE_URL.
    monkeypatch.setenv("CONFIRM_RESTORE_DB", "1")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RESTORE_DATABASE_URL", raising=False)
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmpdir"))
    (tmp_path / "tmpdir").mkdir()
    return tmp_path


def _run_main(module, tmp_path, monkeypatch, capsys, *, backup_file, target_url):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "restore_db.py",
            "--backup-file",
            str(backup_file),
            "--target-database-url",
            target_url,
        ],
    )
    return module.main()


def _sql_backup(tmp_path: Path) -> Path:
    backup = tmp_path / "clinic_backup.sql"
    backup.write_text("SELECT 1;\n", encoding="utf-8")
    return backup


# ── BR-001: psql must stop on the first SQL error ─────────────────────────


def test_psql_restore_command_pins_on_error_stop(restore_env, monkeypatch):
    """The .sql restore command carries -X -v ON_ERROR_STOP=1.

    Pre-fix this is RED: psql was invoked without ON_ERROR_STOP and a
    failed statement still yielded exit 0 + the success marker.
    """

    module = _load_script("restore_db")
    recorded: list[list[str]] = []
    monkeypatch.setattr(module, "postgres_tool", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, **kwargs: recorded.append(list(cmd)) or None,
    )
    backup = _sql_backup(restore_env)
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    _run_main(
        module,
        restore_env,
        monkeypatch,
        None,
        backup_file=backup,
        target_url=target,
    )

    assert len(recorded) == 1
    cmd = recorded[0]
    assert Path(cmd[0]).name.startswith("psql")
    assert "-X" in cmd, "psql must not read psqlrc (BR-001)"
    assert "ON_ERROR_STOP=1" in cmd, "psql must stop on the first SQL error (BR-001)"
    assert cmd[cmd.index("ON_ERROR_STOP=1") - 1] == "-v"
    # the archive is still the -f payload
    assert cmd[cmd.index("-f") + 1] == str(backup)


def test_psql_flags_reach_the_real_subprocess(restore_env, monkeypatch):
    """End-to-end wiring: a recorded fake psql sees the BR-001 flags.

    postgres_tool() honours PSQL_EXE, so the fake binary proves the
    flags survive the real subprocess boundary, not just a mocked
    run_command.
    """

    module = _load_script("restore_db")
    recorded_args = restore_env / "psql_args.txt"
    fake_psql = restore_env / "fake_psql.sh"
    fake_psql.write_text(
        "#!/bin/sh\n" f'printf "%s\\n" "$@" > {recorded_args}\n' "exit 0\n",
        encoding="utf-8",
    )
    fake_psql.chmod(0o755)
    monkeypatch.setenv("PSQL_EXE", str(fake_psql))
    backup = _sql_backup(restore_env)
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    _run_main(
        module,
        restore_env,
        monkeypatch,
        None,
        backup_file=backup,
        target_url=target,
    )

    argv = recorded_args.read_text(encoding="utf-8").splitlines()
    assert "-X" in argv, "BR-001: -X must reach the real psql process"
    assert "ON_ERROR_STOP=1" in argv, "BR-001: ON_ERROR_STOP must reach real psql"


def test_no_success_marker_when_restore_command_fails(restore_env, monkeypatch, capsys):
    """A failing restore command must not emit the success markers."""

    module = _load_script("restore_db")
    from clinic_lifecycle_common import LifecycleError

    monkeypatch.setattr(module, "postgres_tool", lambda name: f"/fake/{name}")

    def _boom(cmd, **kwargs):
        raise LifecycleError("Command failed with exit code 3")

    monkeypatch.setattr(module, "run_command", _boom)
    backup = _sql_backup(restore_env)
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    with pytest.raises(LifecycleError):
        _run_main(
            module,
            restore_env,
            monkeypatch,
            capsys,
            backup_file=backup,
            target_url=target,
        )

    captured = capsys.readouterr()
    assert "RESTORED_BACKUP_FILE=" not in captured.out
    assert "PASS:" not in captured.out


def test_archive_with_invalid_statement_cannot_emit_success(
    restore_env, monkeypatch, capsys
):
    """The audit's BR-001 test-first shape, end to end.

    The fake psql emulates the REAL psql error contract: it exits 0
    after a SQL error when ON_ERROR_STOP is absent (the dangerous
    default), and exits nonzero when the wrapper passes
    ``ON_ERROR_STOP=1`` for an archive containing an invalid statement.

    Pre-fix RED: no flag reached psql, so the fake "completed" the
    restore of a broken archive and the script printed the success
    markers. Post-fix: nonzero exit, no success marker.
    """

    module = _load_script("restore_db")
    fake_psql = restore_env / "fake_psql_semantics.sh"
    fake_psql.write_text(
        "#!/bin/sh\n"
        'for arg in "$@"; do\n'
        '  if [ "$arg" = "ON_ERROR_STOP=1" ]; then\n'
        "    # flag present: emulate psql failing on the invalid statement\n"
        '    for a in "$@"; do\n'
        '      case "$prev" in -f) exit 3 ;; esac\n'
        '      prev="$a"\n'
        "    done\n"
        "    exit 0\n"
        "  fi\n"
        "done\n"
        "exit 0  # the dangerous default: errors do not fail the process\n",
        encoding="utf-8",
    )
    fake_psql.chmod(0o755)
    monkeypatch.setenv("PSQL_EXE", str(fake_psql))

    backup = restore_env / "clinic_backup.sql"
    backup.write_text(
        "CREATE TABLE t(id int);\n"
        "INSERT INTO missing_table VALUES (1);\n"  # invalid statement
        "INSERT INTO t VALUES (1);\n",
        encoding="utf-8",
    )
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    with pytest.raises(Exception) as excinfo:
        _run_main(
            module,
            restore_env,
            monkeypatch,
            capsys,
            backup_file=backup,
            target_url=target,
        )

    assert not isinstance(excinfo.value, SystemExit) or excinfo.value.code != 0
    captured = capsys.readouterr()
    assert "RESTORED_BACKUP_FILE=" not in captured.out, (
        "BR-001: a restore with a failed SQL statement must not print "
        "the success marker"
    )
    assert "PASS:" not in captured.out


def test_pg_restore_branch_contract_unchanged(restore_env, monkeypatch):
    """The custom-format branch stays as-is: BR-011 is a separate fix."""

    module = _load_script("restore_db")
    recorded: list[list[str]] = []
    monkeypatch.setattr(module, "postgres_tool", lambda name: f"/fake/{name}")
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, **kwargs: recorded.append(list(cmd)) or None,
    )
    backup = restore_env / "clinic_backup.dump"
    backup.write_bytes(b"PGDMP\x00synthetic")
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    _run_main(
        module,
        restore_env,
        monkeypatch,
        None,
        backup_file=backup,
        target_url=target,
    )

    cmd = recorded[0]
    assert Path(cmd[0]).name.startswith("pg_restore")
    assert "-c" in cmd and "--if-exists" in cmd
    assert not any(
        "ON_ERROR_STOP" in part for part in cmd
    ), "pg_restore flags are BR-011 scope — do not change them here"


# ── BR-007: a malformed .gz must not leak the plaintext temp file ─────────


def test_truncated_gzip_leaves_no_temp_file_and_no_restore(restore_env, monkeypatch):
    """A truncated archive raises, cleans the temp file, never restores.

    Pre-fix RED: the helper ran before main()'s try/finally, so the
    unencrypted temp SQL dump survived the failure in the OS temp dir.
    """

    module = _load_script("restore_db")
    good = gzip.compress(b"SELECT 1;\n", 9)
    truncated = restore_env / "clinic_backup.sql.gz"
    truncated.write_bytes(good[: len(good) // 2])

    restore_calls: list[list[str]] = []
    monkeypatch.setattr(
        module,
        "run_command",
        lambda cmd, **kwargs: restore_calls.append(list(cmd)) or None,
    )
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    with pytest.raises((OSError, EOFError)):
        _run_main(
            module,
            restore_env,
            monkeypatch,
            None,
            backup_file=truncated,
            target_url=target,
        )

    tempdir = restore_env / "tmpdir"
    leftovers = [p.name for p in tempdir.iterdir()]
    assert leftovers == [], f"BR-007: plaintext temp artifact leaked: {leftovers}"
    assert restore_calls == [], "a failed expansion must never reach psql"


def test_valid_gzip_roundtrip_still_cleans_temp(restore_env, monkeypatch, capsys):
    """The success path keeps working and cleans its temp artifact."""

    module = _load_script("restore_db")
    backup = restore_env / "clinic_backup.sql.gz"
    backup.write_bytes(gzip.compress(b"SELECT 1;\nSELECT 2;\n", 9))

    recorded: list[list[str]] = []
    monkeypatch.setattr(module, "postgres_tool", lambda name: f"/fake/{name}")

    def _fake_restore(cmd, **kwargs):
        recorded.append(list(cmd))

    monkeypatch.setattr(module, "run_command", _fake_restore)
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    _run_main(
        module,
        restore_env,
        monkeypatch,
        capsys,
        backup_file=backup,
        target_url=target,
    )

    assert len(recorded) == 1
    tempdir = restore_env / "tmpdir"
    assert [
        p.name for p in tempdir.iterdir()
    ] == [], "the expanded temp file must be removed after the restore"
    captured = capsys.readouterr()
    assert f"RESTORED_BACKUP_FILE={backup}" in captured.out
    assert "PASS:" in captured.out


@pytest.mark.skipif(os.name != "posix", reason="POSIX file-mode pin")
def test_gzip_temp_artifact_is_owner_only(restore_env, monkeypatch):
    """The plaintext temp artifact keeps restrictive 0600 permissions."""

    module = _load_script("restore_db")
    backup = restore_env / "clinic_backup.sql.gz"
    backup.write_bytes(gzip.compress(b"SELECT 1;\n", 9))

    modes: list[int] = []

    def _fake_restore(cmd, **kwargs):
        payload = Path(cmd[cmd.index("-f") + 1])
        modes.append(stat.S_IMODE(payload.stat().st_mode))

    monkeypatch.setattr(module, "postgres_tool", lambda name: f"/fake/{name}")
    monkeypatch.setattr(module, "run_command", _fake_restore)
    target = "postgresql://user:pw@127.0.0.1:5544/restore_target"

    _run_main(
        module,
        restore_env,
        monkeypatch,
        None,
        backup_file=backup,
        target_url=target,
    )

    assert modes == [0o600], f"plaintext temp must be 0600, got {oct(modes[0])}"

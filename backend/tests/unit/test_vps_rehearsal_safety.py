"""Fail-first guards for the VPS backup/restore/update rehearsal lifecycle scripts.

Repairs BR-002, BR-003, BR-005, BR-009 and BR-011 of the backup/restore
source review (``docs/audits/2026-11-05-backup-restore-source-review.md``,
PR #3882). Every PostgreSQL subprocess is mocked or replaced by recorded
fakes: no real database is contacted, nothing is deployed, no real backup
material is used — only synthetic files in pytest temporary directories.

Coverage:
- BR-002  the backup/restore rehearsal must refuse a restore target that
          resolves to the runtime database through host aliases
          (localhost vs 127.0.0.1), and must never inherit the restore
          script's ``CONFIRM_RESTORE_DB`` live-restore bypass.
- BR-003  the rehearsal must refuse to certify a restore whose HTTP smoke
          cannot prove database binding, unless the operator explicitly
          acknowledges the evidence boundary, and the verdict must carry
          ``RESTORE_SMOKE_DB_BINDING=not-proven``.
- BR-005  an explicitly configured ``PUBLIC_URL`` must win over the default
          LAN auto-detection, and the rehearsal must pin
          ``CLINIC_AUTO_DETECT_PUBLIC_URL=0`` for its smoke children.
- BR-009  the update rehearsal's failure verdict must describe a code-only
          rollback with the database NOT restored, and ``rollback_release``
          must report a code checkout, not a full restore.
- BR-011  ``restore_db.py`` custom-format restores must pin
          ``pg_restore --single-transaction`` (all-or-nothing).
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

import clinic_lifecycle_common as clc  # noqa: E402
import restore_db as rdb  # noqa: E402
import rollback_release as rrel  # noqa: E402
import run_backup_restore_rehearsal as rbrr  # noqa: E402
import run_update_rehearsal as rur  # noqa: E402


def _ok(cmd, stdout: str = "") -> subprocess.CompletedProcess:
    return subprocess.CompletedProcess(cmd, 0, stdout, "")


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """Lifecycle environment without repo env files or live targets."""
    app_root = tmp_path / "repo"
    (app_root / "backend").mkdir(parents=True)
    (app_root / "frontend").mkdir(parents=True)
    monkeypatch.setenv("APP_ROOT", str(app_root))
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("RESTORE_DATABASE_URL", raising=False)
    monkeypatch.delenv("RESTORE_BACKEND_URL", raising=False)
    monkeypatch.delenv("RESTORE_PUBLIC_URL", raising=False)
    monkeypatch.delenv("RESTORE_SMOKE_BINDING_ACK", raising=False)
    monkeypatch.delenv("CONFIRM_RESTORE_DB", raising=False)
    monkeypatch.delenv("PUBLIC_URL", raising=False)
    monkeypatch.delenv("CLINIC_AUTO_DETECT_PUBLIC_URL", raising=False)
    return tmp_path


def _patched_rehearsal(monkeypatch):
    """Record _invoke calls instead of spawning real child scripts."""
    calls: list[tuple[str, dict[str, str] | None, set[str] | None]] = []

    def fake_invoke(script_name, *, extra_env=None, drop_env=None):
        calls.append((script_name, extra_env, drop_env))
        if script_name == "backup_db.py":
            return "BACKUP_FILE=/tmp/synthetic-rehearsal-backup.dump\n"
        return ""

    monkeypatch.setattr(rbrr, "_invoke", fake_invoke)
    return calls


# ---------------------------------------------------------------------------
# BR-002 — alias-equal targets must be refused before any child script runs
# ---------------------------------------------------------------------------


def test_rehearsal_refuses_restore_target_equal_via_host_alias(
    isolated_env, monkeypatch
):
    """BR-002: DATABASE_URL on localhost and RESTORE_DATABASE_URL on
    127.0.0.1 address the same database for the alias guard — the rehearsal
    must fail before creating a backup or touching the target."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://live_user:live_pass@localhost:5432/clinic"
    )
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/clinic",
    )
    monkeypatch.setenv("RESTORE_BACKEND_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_PUBLIC_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_SMOKE_BINDING_ACK", "1")

    calls = _patched_rehearsal(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        rbrr.main()

    assert excinfo.value.code != 0, "alias-equal restore target must be refused"
    assert calls == [], (
        "the rehearsal ran child scripts although the restore target aliases "
        f"the runtime database (invoked: {[c[0] for c in calls]})"
    )


def test_rehearsal_allows_genuinely_separate_target(isolated_env, monkeypatch):
    """BR-002 keeper: a distinct target (different host class and name) proceeds."""
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql://live_user:live_pass@db.internal:5432/clinic"
    )
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/restore_db",
    )
    monkeypatch.setenv("RESTORE_BACKEND_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_PUBLIC_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_SMOKE_BINDING_ACK", "1")

    calls = _patched_rehearsal(monkeypatch)
    assert rbrr.main() == 0
    assert [c[0] for c in calls] == [
        "backup_db.py",
        "restore_db.py",
        "health_check.py",
        "smoke_post_update.py",
    ]


def test_rehearsal_does_not_inherit_live_restore_confirmation(
    isolated_env, monkeypatch
):
    """BR-002: ``CONFIRM_RESTORE_DB=1`` in the rehearsal environment must not
    leak into the restore_db.py child — the rehearsal never restores live."""
    monkeypatch.setenv("CONFIRM_RESTORE_DB", "1")
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/restore_db",
    )
    monkeypatch.setenv("RESTORE_BACKEND_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_PUBLIC_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_SMOKE_BINDING_ACK", "1")

    calls = _patched_rehearsal(monkeypatch)
    assert rbrr.main() == 0

    restore_call = next(c for c in calls if c[0] == "restore_db.py")
    assert (
        restore_call[2] is not None and "CONFIRM_RESTORE_DB" in restore_call[2]
    ), "the rehearsal must drop CONFIRM_RESTORE_DB from the restore child env"


# ---------------------------------------------------------------------------
# BR-003 — smoke binding evidence boundary must be explicit
# ---------------------------------------------------------------------------


def test_rehearsal_requires_smoke_binding_acknowledgment(isolated_env, monkeypatch):
    """BR-003: without RESTORE_SMOKE_BINDING_ACK=1 the rehearsal must refuse
    to certify a restore whose smoke cannot prove database binding."""
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/restore_db",
    )
    monkeypatch.setenv("RESTORE_BACKEND_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_PUBLIC_URL", "http://127.0.0.1:18001")
    # no RESTORE_SMOKE_BINDING_ACK

    calls = _patched_rehearsal(monkeypatch)

    with pytest.raises(SystemExit) as excinfo:
        rbrr.main()

    assert (
        excinfo.value.code != 0
    ), "missing binding acknowledgment must fail the rehearsal"
    assert calls == [], "no child script may run before the binding acknowledgment"


def test_rehearsal_verdict_marks_smoke_binding_not_proven(
    isolated_env, monkeypatch, capsys
):
    """BR-003: the success verdict must carry an explicit not-proven binding
    marker instead of silently implying a full recovery proof."""
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/restore_db",
    )
    monkeypatch.setenv("RESTORE_BACKEND_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_PUBLIC_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_SMOKE_BINDING_ACK", "1")

    _patched_rehearsal(monkeypatch)
    assert rbrr.main() == 0

    out = capsys.readouterr().out
    assert (
        "RESTORE_SMOKE_DB_BINDING=not-proven" in out
    ), "the verdict must state that the smoke does not prove DB binding"


# ---------------------------------------------------------------------------
# BR-005 — explicit PUBLIC_URL must win over LAN auto-detection
# ---------------------------------------------------------------------------


def test_explicit_public_url_wins_over_autodetect(monkeypatch):
    """BR-005: with PUBLIC_URL explicitly set, public_url() must return it —
    the default-on LAN auto-detection must not override the operator's URL."""
    monkeypatch.setattr(clc, "_detect_lan_ip", lambda: "10.99.99.99")
    monkeypatch.setenv("PUBLIC_URL", "http://127.0.0.1:18001")
    # CLINIC_AUTO_DETECT_PUBLIC_URL deliberately unset — default is True.

    assert (
        clc.public_url() == "http://127.0.0.1:18001"
    ), "auto-detection overrode an explicitly configured PUBLIC_URL"


def test_rehearsal_pins_auto_detect_off_for_smoke_children(isolated_env, monkeypatch):
    """BR-005: the rehearsal must pass CLINIC_AUTO_DETECT_PUBLIC_URL=0 to the
    smoke children so a LAN auto-detect can never replace RESTORE_PUBLIC_URL."""
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/restore_db",
    )
    monkeypatch.setenv("RESTORE_BACKEND_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_PUBLIC_URL", "http://127.0.0.1:18001")
    monkeypatch.setenv("RESTORE_SMOKE_BINDING_ACK", "1")

    calls = _patched_rehearsal(monkeypatch)
    assert rbrr.main() == 0

    for script in ("health_check.py", "smoke_post_update.py"):
        call = next(c for c in calls if c[0] == script)
        extra = call[1] or {}
        assert (
            extra.get("CLINIC_AUTO_DETECT_PUBLIC_URL") == "0"
        ), f"{script} must run with restore-scoped origin resolution pinned"


# ---------------------------------------------------------------------------
# BR-009 — rollback verdict must be code-only, database NOT restored
# ---------------------------------------------------------------------------


def test_update_rehearsal_failure_verdict_is_code_only(monkeypatch, capsys):
    """BR-009: after a handled rollback the rehearsal must print explicit
    code-only scope markers and must never imply a restored database."""
    invoked: list[str] = []

    def fake_invoke(script_name, *, extra_env=None):
        invoked.append(script_name)
        if script_name == "backup_db.py":
            return "BACKUP_FILE=/tmp/synthetic-pre-update-backup.dump\n"
        return ""

    monkeypatch.setattr(rur, "_invoke", fake_invoke)

    def unreachable(*_args, **_kwargs):
        raise clc.LifecycleError("synthetic: backend never reachable")

    monkeypatch.setattr(rur, "http_json", unreachable)
    monkeypatch.setattr(rur.time, "sleep", lambda _s: None)
    monkeypatch.setenv("UPDATE_RELEASE_REF", "synthetic-release")

    calls = {"n": 0}

    def fake_monotonic() -> float:
        calls["n"] += 1
        return 100.0 * calls["n"]

    monkeypatch.setattr(rur.time, "monotonic", fake_monotonic)

    with pytest.raises(SystemExit) as excinfo:
        rur.main()

    assert excinfo.value.code != 0
    assert "rollback_release.py" in invoked

    captured = capsys.readouterr()
    combined = captured.out + captured.err
    assert (
        "UPDATE_ROLLBACK_SCOPE=code-only" in combined
    ), "the rollback verdict must declare code-only scope"
    assert (
        "UPDATE_DATABASE_RESTORED=no" in combined
    ), "the verdict must state the database was not restored"
    assert (
        "UPDATE_BACKUP_FILE_FOR_MANUAL_RESTORE=/tmp/synthetic-pre-update-backup.dump"
        in combined
    ), "the verdict must name the pre-update backup for the manual protocol"


def test_rollback_release_reports_code_checkout_not_restore(
    isolated_env, monkeypatch, capsys
):
    """BR-009: rollback_release.py checks out code — its PASS verdict must
    not read as a full restore."""
    commands: list[list[str]] = []

    def fake_run_command(args, **_kwargs):
        commands.append([str(a) for a in args])
        return _ok(args)

    monkeypatch.setattr(rrel, "run_command", fake_run_command)
    monkeypatch.setenv("ROLLBACK_REF", "synthetic-rollback-ref")
    monkeypatch.delenv("ROLLBACK_RUN_MIGRATIONS", raising=False)

    assert rrel.main() == 0

    out = capsys.readouterr().out
    assert "code rollback only" in out, "the verdict must declare a code-only rollback"
    assert (
        "database schema not reverted" in out
    ), "the verdict must state the database schema was not reverted"
    assert (
        "restored" not in out.split("PASS:")[1].lower()
    ), "the PASS line still claims a restore"


# ---------------------------------------------------------------------------
# BR-011 — custom-format restore must be transactional
# ---------------------------------------------------------------------------


def test_restore_db_pins_single_transaction_for_pg_restore(
    isolated_env, monkeypatch, tmp_path
):
    """BR-011: ``restore_db.py`` custom-format (``pg_restore``) path must pin
    ``--single-transaction`` so a mid-restore failure leaves the target
    unmodified instead of partly dropped/recreated."""
    backup = tmp_path / "synthetic_backup.dump"
    backup.write_bytes(b"PGDMP-SYNTHETIC-ARCHIVE")

    recorded: list[list[str]] = []

    def fake_run_command(args, **_kwargs):
        recorded.append([str(a) for a in args])
        return _ok(args)

    monkeypatch.setattr(rdb, "run_command", fake_run_command)
    monkeypatch.setattr(rdb, "postgres_tool", lambda name: f"synthetic_{name}")
    monkeypatch.setattr(sys, "argv", ["restore_db.py"])
    monkeypatch.setenv("BACKUP_FILE", str(backup))
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/restore_db",
    )
    monkeypatch.setenv(
        "CONFIRM_RESTORE_DB", "1"
    )  # direct deliberate use, no runtime DATABASE_URL

    assert rdb.main() == 0

    pg_cmd = next(cmd for cmd in recorded if "pg_restore" in cmd[0])
    assert "--single-transaction" in pg_cmd, (
        "custom-format restore must be all-or-nothing (--single-transaction); "
        f"got: {pg_cmd}"
    )
    assert (
        "-c" in pg_cmd and "--if-exists" in pg_cmd
    ), f"clean-if-exists semantics lost: {pg_cmd}"


def test_restore_db_keeps_psql_path_untouched(isolated_env, monkeypatch, tmp_path):
    """BR-011 keeper: the plain-SQL psql path is BR-001's scope (#3883) and
    must not receive pg_restore-only flags."""
    backup = tmp_path / "synthetic_backup.sql"
    backup.write_bytes(b"SELECT 1;")

    recorded: list[list[str]] = []

    def fake_run_command(args, **_kwargs):
        recorded.append([str(a) for a in args])
        return _ok(args)

    monkeypatch.setattr(rdb, "run_command", fake_run_command)
    monkeypatch.setattr(rdb, "postgres_tool", lambda name: f"synthetic_{name}")
    monkeypatch.setattr(sys, "argv", ["restore_db.py"])
    monkeypatch.setenv("BACKUP_FILE", str(backup))
    monkeypatch.setenv(
        "RESTORE_DATABASE_URL",
        "postgresql://restore_user:restore_pwd@127.0.0.1:5432/restore_db",
    )
    monkeypatch.setenv("CONFIRM_RESTORE_DB", "1")

    assert rdb.main() == 0

    psql_cmd = next(cmd for cmd in recorded if "psql" in cmd[0])
    assert "--single-transaction" not in psql_cmd

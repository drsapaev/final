"""Fail-first proofs for repair group 2 of the backup/restore source review.

Implements the acceptance order from
``docs/audits/2026-11-05-backup-restore-source-review.md`` (PR #3882):
the six-test fail-first draft — BR-008, BR-012, BR-013, BR-016, BR-017
and BR-018 — placed under the backend test tree, run against the real
modules, and paired with the narrow fail-closed fixes in the same PR.

- **BR-008 (P1):** the update-rehearsal readiness timeout raised
  ``SystemExit`` via ``fail()``; the rollback supervisor catches only
  ``Exception``, so a timeout AFTER deploy/migration skipped the
  automatic rollback entirely.
- **BR-012 (P1, conditional high-impact):** ``DRILL_DB_NAME`` was never
  compared with the source database and was interpolated into quoted
  SQL raw — a misconfigured name could make the drill drop the source.
- **BR-013 (P1 candidate):** drill subprocess exit statuses were
  ignored (``check=False`` + stderr-``ERROR:`` sniffing), so failed
  DROP/CREATE/restore could certify a stale database.
- **BR-016 (P1 candidate):** gzip drill extraction wrote
  ``backup.with_suffix("")`` in the backup's own directory — an
  adjacent same-stem archive was truncated and plaintext could remain.
- **BR-017 (P1 candidate):** the finally-cleanup dropped the drill DB
  even when the run never created it.
- **BR-018 (P1 candidate):** a failed service backup unlinked EVERY
  ``*.tmp`` in the backup directory — another concurrent writer's live
  staging archive included.

No PostgreSQL required: subprocess execution is faked at the module
boundary; only synthetic files are used. Per the audit's stop
condition, the drill must NOT be executed with credentials capable of
dropping a live clinic DB while these guards are unfixed.
"""

from __future__ import annotations

import gzip
import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

BACKEND_ROOT = Path(__file__).resolve().parents[2]
OPS_SCRIPTS = BACKEND_ROOT.parent / "ops" / "vps" / "scripts"


def _load_ops_script(name: str):
    if str(OPS_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(OPS_SCRIPTS))
    spec = importlib.util.spec_from_file_location(
        f"br_fail_first_{name}", OPS_SCRIPTS / f"{name}.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── DR drill harness (BR-012/013/016/017) ──────────────────────────────────


class CommandRecorder:
    """Fakes dr_drill._run, records every command, resolves results."""

    def __init__(self, resolver=None):
        self.calls: list[list[str]] = []
        self._resolver = resolver or (lambda cmd: (0, "5", ""))

    def __call__(self, cmd, env=None, check=True):
        self.calls.append(list(cmd))
        rc, out, err = self._resolver(cmd)
        return subprocess.CompletedProcess(cmd, rc, stdout=out, stderr=err)


def _setup_drill(
    monkeypatch,
    tmp_path,
    *,
    drill_db_name,
    source_db="clinicdb",
    drop_on_start=True,
    keep_db=False,
):
    import app.scripts.dr_drill as dr_drill

    monkeypatch.setattr(dr_drill, "DRILL_DB_NAME", drill_db_name)
    monkeypatch.setattr(dr_drill, "DRILL_DB_DROP_ON_START", drop_on_start)
    monkeypatch.setattr(dr_drill, "ensure_pg_tools", lambda: None)
    monkeypatch.setattr(
        dr_drill,
        "parse_source_db_url",
        lambda: ("postgres", "pw", "127.0.0.1", 5543, source_db),
    )
    monkeypatch.delenv("DRILL_KEEP_DB", raising=False)
    if keep_db:
        monkeypatch.setenv("DRILL_KEEP_DB", "1")

    backup_dir = tmp_path / "backups"
    backup_dir.mkdir(exist_ok=True)
    backup = backup_dir / "synthetic.dump"
    backup.write_bytes(b"PGDMP-synthetic")
    monkeypatch.setenv("BACKUP_FILE", str(backup))
    return dr_drill


def test_br012_drill_refuses_source_name_collision_before_any_command(
    tmp_path, monkeypatch
):
    """BR-012: source == drill target exits BEFORE any psql/DROP/CREATE."""

    dr_drill = _setup_drill(
        monkeypatch, tmp_path, drill_db_name="clinicdb", source_db="clinicdb"
    )
    recorder = CommandRecorder()
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code != 0
    assert recorder.calls == [], (
        f"BR-012: destructive command issued despite the identity "
        f"collision: {[c[0] for c in recorder.calls]}"
    )


def test_br012_drill_rejects_non_identifier_target_names(tmp_path, monkeypatch):
    """BR-012: env text with SQL delimiters never reaches quoted SQL."""

    dr_drill = _setup_drill(
        monkeypatch, tmp_path, drill_db_name='clinic"; DROP DATABASE x; --'
    )
    recorder = CommandRecorder()
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code == 2
    assert recorder.calls == [], "a non-identifier target reached psql"


def test_br013_failed_drop_stops_the_drill_before_create(tmp_path, monkeypatch):
    """BR-013: a failed DROP DATABASE is fatal, CREATE never runs."""

    dr_drill = _setup_drill(monkeypatch, tmp_path, drill_db_name="clinic_dr_drill")

    def resolver(cmd):
        if "DROP DATABASE" in cmd[-1]:
            return (1, "", "fake: DROP failed")
        return (0, "5", "")

    recorder = CommandRecorder(resolver)
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code == 1
    creates = [c for c in recorder.calls if "CREATE DATABASE" in c[-1]]
    assert creates == [], "CREATE ran after a failed DROP"


def test_br013_failed_create_stops_the_drill_before_restore(tmp_path, monkeypatch):
    """BR-013: a failed CREATE DATABASE is fatal, pg_restore never runs."""

    dr_drill = _setup_drill(monkeypatch, tmp_path, drill_db_name="clinic_dr_drill")

    def resolver(cmd):
        if "CREATE DATABASE" in cmd[-1]:
            return (1, "", "fake: CREATE failed")
        return (0, "5", "")

    recorder = CommandRecorder(resolver)
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code == 1
    restores = [c for c in recorder.calls if c[0] == "pg_restore"]
    assert restores == [], "pg_restore ran against a database that was never created"


def test_br013_nonzero_pg_restore_fails_even_without_error_token(tmp_path, monkeypatch):
    """BR-013: returncode is authoritative, stderr shape is not."""

    dr_drill = _setup_drill(monkeypatch, tmp_path, drill_db_name="clinic_dr_drill")

    def resolver(cmd):
        if cmd[0] == "pg_restore":
            # the audit's exact shape: nonzero, no 'ERROR:' token
            return (1, "", "pg_restore: connection interrupted")
        return (0, "5", "")

    recorder = CommandRecorder(resolver)
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert (
        excinfo.value.code == 1
    ), "BR-013: a nonzero pg_restore without an ERROR: line must fail the drill"


def test_br016_gzip_extraction_never_touches_an_adjacent_archive(tmp_path, monkeypatch):
    """BR-016: same-stem .dump next to .dump.gz stays byte-identical."""

    import app.scripts.dr_drill as dr_drill

    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmpdir"))
    (tmp_path / "tmpdir").mkdir()

    workdir = tmp_path / "backups"
    workdir.mkdir()
    sentinel = workdir / "synthetic.dump"
    sentinel.write_bytes(b"ORIGINAL-SENTINEL-BYTES")
    archive = workdir / "synthetic.dump.gz"
    archive.write_bytes(gzip.compress(b"PGDMP-DECOMPRESSED-CONTENT"))

    recorder = CommandRecorder()
    monkeypatch.setattr(dr_drill, "_run", recorder)

    dr_drill.restore_backup(archive, "u", "p", "127.0.0.1", 5543)

    assert (
        sentinel.read_bytes() == b"ORIGINAL-SENTINEL-BYTES"
    ), "BR-016: gzip extraction truncated the adjacent same-stem archive"
    assert sorted(p.name for p in workdir.iterdir()) == [
        "synthetic.dump",
        "synthetic.dump.gz",
    ]
    assert [
        p.name for p in (tmp_path / "tmpdir").iterdir()
    ] == [], "BR-016: the extracted plaintext artifact was not cleaned up"
    assert recorder.calls[0][0] == "pg_restore"


def test_br016_truncated_gzip_leaves_no_plaintext_anywhere(tmp_path, monkeypatch):
    """BR-016: a malformed stream cleans its temp artifact and fails."""

    import app.scripts.dr_drill as dr_drill

    monkeypatch.setattr("tempfile.tempdir", str(tmp_path / "tmpdir"))
    (tmp_path / "tmpdir").mkdir()

    workdir = tmp_path / "backups"
    workdir.mkdir()
    sentinel = workdir / "synthetic.dump"
    sentinel.write_bytes(b"ORIGINAL-SENTINEL-BYTES")
    archive = workdir / "synthetic.dump.gz"
    archive.write_bytes(gzip.compress(b"PGDMP-DECOMPRESSED-CONTENT")[:6])

    recorder = CommandRecorder()
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises((OSError, EOFError)):
        dr_drill.restore_backup(archive, "u", "p", "127.0.0.1", 5543)

    assert sentinel.read_bytes() == b"ORIGINAL-SENTINEL-BYTES"
    assert [p.name for p in workdir.iterdir()] == [
        "synthetic.dump",
        "synthetic.dump.gz",
    ]
    assert [
        p.name for p in (tmp_path / "tmpdir").iterdir()
    ] == [], "BR-016: partial plaintext left in the temp directory"
    assert recorder.calls == [], "a failed extraction must never reach pg_restore"


def test_br017_cleanup_never_drops_a_database_this_run_did_not_create(
    tmp_path, monkeypatch
):
    """BR-017: failed CREATE + DRILL_DB_DROP_ON_START=0 → no DROP at all."""

    dr_drill = _setup_drill(
        monkeypatch, tmp_path, drill_db_name="clinic_dr_drill", drop_on_start=False
    )

    def resolver(cmd):
        if "CREATE DATABASE" in cmd[-1]:
            return (1, "", "fake: CREATE failed (target exists)")
        return (0, "5", "")

    recorder = CommandRecorder(resolver)
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code == 1
    drops = [c for c in recorder.calls if "DROP DATABASE" in c[-1]]
    assert (
        drops == []
    ), "BR-017: cleanup dropped a preexisting target this run never created"


def test_br017_drill_keep_db_still_preserves_the_scratch_explicitly(
    tmp_path, monkeypatch
):
    """Pin: DRILL_KEEP_DB=1 keeps the created scratch DB (intentional)."""

    dr_drill = _setup_drill(
        monkeypatch, tmp_path, drill_db_name="clinic_dr_drill", keep_db=True
    )
    recorder = CommandRecorder()
    monkeypatch.setattr(dr_drill, "_run", recorder)

    with pytest.raises(SystemExit):
        dr_drill.main()

    drops_after_create = [
        c
        for c in recorder.calls
        if "DROP DATABASE" in c[-1]
        and recorder.calls.index(c)
        > recorder.calls.index(
            next(c2 for c2 in recorder.calls if "CREATE DATABASE" in c2[-1])
        )
    ]
    assert drops_after_create == [], "DRILL_KEEP_DB=1 must retain the drill DB"


# ── BR-008: update-rehearsal rollback supervision ──────────────────────────


def test_br008_readiness_timeout_triggers_rollback(tmp_path, monkeypatch):
    """A readiness timeout must reach the rollback supervisor, not skip it.

    Pre-fix RED: ``fail()`` raised SystemExit — a BaseException the
    supervisor's ``except Exception`` does not catch — so the rollback
    never ran after a post-migration timeout.
    """

    module = _load_ops_script("run_update_rehearsal")
    app_root = tmp_path / "repo"
    (app_root / "backend").mkdir(parents=True)
    monkeypatch.setenv("APP_ROOT", str(app_root))
    monkeypatch.setenv("UPDATE_RELEASE_REF", "v9.9.9-test")
    monkeypatch.delenv("ROLLBACK_REF", raising=False)
    monkeypatch.delenv("ROLLBACK_RUN_MIGRATIONS", raising=False)
    monkeypatch.setattr(module, "load_clinic_env", lambda: None)
    monkeypatch.setattr(module, "git_head", lambda root=None: "baseline123")

    invoked: list[str] = []

    def _fake_invoke(script_name, *, extra_env=None):
        invoked.append(script_name)
        if script_name == "backup_db.py":
            return f"BACKUP_FILE={tmp_path / 'synthetic.dump'}\n"
        return ""

    monkeypatch.setattr(module, "_invoke", _fake_invoke)

    # the readiness loop: one failing probe, then the deadline is over
    clock = {"t": 0.0}

    def _mono():
        clock["t"] += 1000.0
        return clock["t"]

    monkeypatch.setattr(
        module, "time", SimpleNamespace(monotonic=_mono, sleep=lambda s: None)
    )
    monkeypatch.setattr(
        module,
        "http_json",
        lambda *a, **k: (503, None, "synthetic: backend down"),
    )

    with pytest.raises(SystemExit):
        module.main()

    assert (
        "rollback_release.py" in invoked
    ), "BR-008: the readiness timeout bypassed the rollback supervisor"
    assert invoked.index("run_migrations.py") < invoked.index("rollback_release.py")


# ── BR-018: service backup staging ownership ───────────────────────────────


def test_br018_failed_backup_never_deletes_other_writers_temp(tmp_path, monkeypatch):
    """A failing writer removes ONLY its own staging file."""

    import app.services.backup_service as backup_service

    svc = backup_service.BackupService.__new__(backup_service.BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 10

    monkeypatch.setattr(
        backup_service,
        "_get_database_url",
        lambda: "postgresql://admin:pw@127.0.0.1:5543/clinicdb",
    )
    monkeypatch.setattr(
        backup_service, "_resolve_pg_tool", lambda tool: f"/fake/{tool}"
    )

    other_writer_tmp = tmp_path / "backup_manual_99990101_000000.db.tmp"
    other_writer_tmp.write_bytes(b"OTHER-WRITER-IN-FLIGHT")

    def _failing_dump(cmd, env=None, capture_output=True, text=True, check=False):
        # writer A starts producing bytes into ITS staging file, then fails
        Path(cmd[cmd.index("-f") + 1]).write_bytes(b"PARTIAL-ARCHIVE")
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="pg_dump: boom")

    monkeypatch.setattr(backup_service.subprocess, "run", _failing_dump)

    with pytest.raises(Exception, match="pg_dump failed"):
        svc.create_backup("manual")

    assert (
        other_writer_tmp.exists()
    ), "BR-018: the failed writer deleted another worker's live staging file"
    assert (
        other_writer_tmp.read_bytes() == b"OTHER-WRITER-IN-FLIGHT"
    ), "BR-018: the failed writer truncated another worker's live staging file"
    assert list(tmp_path.glob("*.tmp")) == [
        other_writer_tmp
    ], "BR-018: exactly the failed operation's staging file must be removed"

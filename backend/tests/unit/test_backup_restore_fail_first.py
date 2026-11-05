"""Fail-first regression drafts for backup/restore findings BR-008/012/013/016/017/018.

Derived from ``docs/audits/2026-11-05-backup-restore-source-review.md``
(Pull Request #3882). Every PostgreSQL subprocess command is mocked in this
module: no real ``DROP DATABASE``, ``CREATE DATABASE``, ``pg_restore`` or
``psql`` is ever executed, no real database is contacted, and no real backup
material is used — only synthetic files in pytest temporary directories.

The BR-008/012/013/016/017/018 fixes landed in Pull Request #3887 (merged
2026-11-05). The post-merge review of #3887 found two remaining P1 defects;
their fail-first regressions live at the bottom of this module in the same
mocked-subprocess style.

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
- PMR-1 (post-merge review of #3887, P1 #1)  the BR-012 collision guard must
          compare the percent-DECODED source DB name, so an encoded DSN
          (``clinic%5Fdr%5Fdrill`` == ``clinic_dr_drill``) cannot bypass it.
- PMR-2 (post-merge review of #3887, P1 #2)  two same-type backups started
          within one second must get unique temp files, exclusive final
          names and failure isolation; retention must never sweep another
          writer's in-flight ``*.tmp``.
- PMR-3 (post-merge review of #3888, P1)  gzip compression must stream into
          a run-private ``.gz.tmp`` and publish atomically — a partial
          archive must never be visible under the final ``.db.gz`` name,
          and a failed compression must leave nothing behind.
- PMR-4 (post-merge review of #3888, P2)  the per-run id must be reserved
          exclusively (``O_CREAT|O_EXCL`` with reroll): forced identical
          run ids must never share a temp path, and publication must never
          clobber an already-completed archive.
- PMR-5 (second-pass review of #3888, P1)  on filesystems without hard
          links the publish fallback must still be no-replace: a repeated
          candidate name must never overwrite a completed archive.
- PMR-6 (second-pass review of #3888, P1)  dumps, temp artifacts and
          published archives must be owner-only (0600) regardless of umask.
- PMR-7 (second-pass review of #3888, P2)  DR-drill discovery must select
          only PUBLISHED archives — in-flight ``.db.tmp``/``.db.gz.tmp``
          artifacts are newer and must never be picked for restore.
- PMR-8 (second-pass review of #3888, P2)  a FileExistsError during
          ``.db.gz`` publication must keep the published-format suffix
          (token BEFORE the compound ``.db.gz``) so the archive stays
          visible to ``list_backups()`` and retention enumeration.
"""

from __future__ import annotations

import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
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
            result = subprocess.CompletedProcess(
                cmd, 1, "", 'ERROR: database "preexisting_target" already exists\n'
            )
            if check:
                # emulate subprocess.run(check=True) contract
                raise subprocess.CalledProcessError(result.returncode, cmd, stderr=result.stderr)
            return result
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
    """BR-018: when backup A fails mid-dump, its cleanup may remove only A's
    own temp file — not every ``*.tmp`` in the shared backup directory."""
    other = tmp_path / "backup_scheduled_20990101_999999.db.tmp"
    other.write_bytes(b"OTHER-WRITER-IN-FLIGHT")

    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 10
    svc.db = None

    monkeypatch.setattr(
        backup_service_module,
        "_get_database_url",
        lambda: "postgresql://drill_user:drill_pass@localhost:5432/clinicdb_src",
    )
    monkeypatch.setattr(
        backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}"
    )

    own_targets: list[Path] = []

    def failing_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        # Simulate a pg_dump that starts writing, creates a partial temp
        # archive, and then fails (audit quality-note scenario).
        if "pg_dump" in str(cmd[0]):
            target = Path(cmd[list(cmd).index("-f") + 1])
            target.write_bytes(b"PARTIAL-SYNTHETIC-DUMP")
            own_targets.append(target)
            return subprocess.CompletedProcess(cmd, 1, "", "pg_dump: synthetic failure")
        raise AssertionError(f"unexpected subprocess call: {cmd}")

    monkeypatch.setattr(backup_service_module.subprocess, "run", failing_pg_dump)

    with pytest.raises(Exception):
        svc.create_backup("manual")

    assert len(own_targets) == 1, "pg_dump stub must have produced one temp artifact"
    own = own_targets[0]
    assert own.exists() is False, "the failed writer must remove its own temp file"
    assert other.exists(), "cleanup deleted another writer's in-flight temp file"
    assert other.read_bytes() == b"OTHER-WRITER-IN-FLIGHT", (
        "cleanup corrupted another writer's in-flight temp file"
    )


# ---------------------------------------------------------------------------
# PMR-1 — post-merge review of #3887 (P1 #1): the BR-012 guard must compare
# the percent-DECODED source DB name.
# ---------------------------------------------------------------------------


def test_parse_source_db_url_decodes_percent_encoding(monkeypatch):
    """PMR-1: ``clinic%5Fdr%5Fdrill`` in DATABASE_URL IS ``clinic_dr_drill``
    to PostgreSQL — ``parse_source_db_url`` must return the decoded name or
    the BR-012 collision guard compares apples to oranges."""
    from app.core.config import settings

    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://drill_user:drill_pass@drill_host.invalid:5432/clinic%5Fdr%5Fdrill",
    )

    user, password, host, port, source_db = dr_drill.parse_source_db_url()

    assert source_db == "clinic_dr_drill", (
        "source DB name must be percent-decoded before the BR-012 comparison"
    )
    assert (user, password, host, port) == (
        "drill_user",
        "drill_pass",
        "drill_host.invalid",
        5432,
    )


def test_dr_drill_refuses_target_db_equal_to_percent_encoded_source_db(
    tmp_path, monkeypatch
):
    """PMR-1 end-to-end: DRILL_DB_NAME equal to the DECODED source DB name
    must abort the drill before any ``DROP DATABASE``, even when DATABASE_URL
    percent-encodes the name (``%5F`` for ``_``). Pre-fix, the raw string
    comparison ``'clinic_dr_drill' == 'clinic%5Fdr%5Fdrill'`` misses the
    collision and the drill drops the working database."""
    from app.core.config import settings

    backup = tmp_path / "synthetic.dump"
    backup.write_bytes(b"SYNTHETIC-ARCHIVE")

    issued: list[list[str]] = []

    def fake_run(cmd, env=None, check=True):
        issued.append([str(part) for part in cmd])
        # smoke queries return plausible row counts
        return _ok(cmd, stdout="3\n")

    monkeypatch.setattr(dr_drill, "_run", fake_run)
    monkeypatch.setattr(dr_drill, "find_latest_backup", lambda: backup)
    monkeypatch.setattr(dr_drill, "ensure_pg_tools", lambda: None)
    monkeypatch.setattr(dr_drill, "DRILL_DB_NAME", "clinic_dr_drill")
    monkeypatch.setattr(dr_drill, "DRILL_DB_DROP_ON_START", True)
    # NOTE: no _drill_env() here — the REAL parse_source_db_url must run
    # against an encoded DSN.
    monkeypatch.setattr(
        settings,
        "DATABASE_URL",
        "postgresql://drill_user:drill_pass@drill_host.invalid:5432/clinic%5Fdr%5Fdrill",
    )

    with pytest.raises(SystemExit) as excinfo:
        dr_drill.main()

    assert excinfo.value.code != 0, (
        "percent-encoded source DB name bypassed the BR-012 collision guard"
    )
    joined = [" ".join(cmd) for cmd in issued]
    assert not any("DROP DATABASE" in cmd for cmd in joined), (
        "drill issued a DROP DATABASE against the working database although "
        f"the decoded names collide (commands: {joined})"
    )


# ---------------------------------------------------------------------------
# PMR-2 — post-merge review of #3887 (P1 #2): parallel same-type backups must
# not corrupt each other (shared second-precision temp path, non-exclusive
# publication, retention sweeping in-flight temp files).
# ---------------------------------------------------------------------------


class _FrozenDatetime(datetime):
    """Clock pinned to one second so two concurrent runs derive the exact
    stem from the reviewed P1 scenario (same type, same second)."""

    @classmethod
    def now(cls, tz=None):  # noqa: ARG003 — mirrors datetime.now signature
        return cls(2026, 11, 6, 12, 0, 0, tzinfo=UTC)


def _concurrent_svc(tmp_path: Path, monkeypatch) -> BackupService:
    """BackupService wired for PG-path concurrency tests: synthetic dump
    tool, no offsite upload, no gzip, frozen clock."""
    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 10
    svc.db = None

    monkeypatch.setattr(
        backup_service_module,
        "_get_database_url",
        lambda: "postgresql://drill_user:drill_pass@localhost:5432/clinicdb_src",
    )
    monkeypatch.setattr(
        backup_service_module, "_resolve_pg_tool", lambda name: f"synthetic_{name}"
    )
    monkeypatch.setattr(
        backup_service_module.r2_uploader, "r2_configured", lambda: False
    )
    monkeypatch.setattr(backup_service_module, "datetime", _FrozenDatetime)
    monkeypatch.setenv("BACKUP_COMPRESS", "false")
    return svc


def test_concurrent_same_type_backups_get_unique_files(tmp_path, monkeypatch):
    """PMR-2: two same-type backups started within the same second must (a)
    dump into distinct temp paths, (b) both publish intact archives under
    distinct final names, (c) leave no temp leftovers."""
    svc = _concurrent_svc(tmp_path, monkeypatch)

    dump_barrier = threading.Barrier(2)
    seq_lock = threading.Lock()
    targets: list[Path] = []

    def fake_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        assert "pg_dump" in str(cmd[0]), f"unexpected subprocess call: {cmd}"
        target = Path(cmd[list(cmd).index("-f") + 1])
        with seq_lock:
            seq = len(targets)
            targets.append(target)
        # Force a true overlap of the two in-flight dumps (same second is
        # already guaranteed by the frozen clock).
        try:
            dump_barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass  # the other run already failed — let this one proceed
        target.write_bytes(f"SYNTHETIC-DUMP-{seq}".encode())
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_pg_dump)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(svc.create_backup, "manual") for _ in range(2)]
        infos = [f.result(timeout=30) for f in futures]

    assert len({str(t) for t in targets}) == 2, (
        f"concurrent runs shared one temp path: {targets}"
    )
    filenames = [info["filename"] for info in infos]
    assert len(set(filenames)) == 2, (
        f"runs published the same final archive name: {filenames}"
    )
    for name in filenames:
        assert name.startswith("backup_manual_20261106_120000"), (
            f"unexpected archive stem: {name}"
        )
        assert (tmp_path / name).exists(), f"published archive missing: {name}"
    finals = sorted(tmp_path.glob("backup_manual_20261106_120000*.db"))
    assert {p.read_bytes() for p in finals} == {b"SYNTHETIC-DUMP-0", b"SYNTHETIC-DUMP-1"}, (
        "a concurrent run corrupted or replaced another run's archive content"
    )
    assert list(tmp_path.glob("*.tmp")) == [], "temp leftovers after successful runs"


def test_failing_concurrent_backup_spares_the_in_flight_run(tmp_path, monkeypatch):
    """PMR-2: a run that fails mid-dump must neither delete nor overwrite the
    temp artifact of another run that is still in flight."""
    svc = _concurrent_svc(tmp_path, monkeypatch)

    inflight_started = threading.Event()
    release_inflight = threading.Event()
    calls = {"n": 0}

    def fake_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        assert "pg_dump" in str(cmd[0]), f"unexpected subprocess call: {cmd}"
        target = Path(cmd[list(cmd).index("-f") + 1])
        calls["n"] += 1
        if calls["n"] == 1:
            # Run A: writes its full archive, then stalls mid-run so run B
            # can fail-and-clean inside the overlap window.
            target.write_bytes(b"SYNTHETIC-DUMP-A")
            inflight_started.set()
            assert release_inflight.wait(timeout=10), "run A stalled forever"
            return subprocess.CompletedProcess(cmd, 0, "", "")
        # Run B: starts while A is in flight, writes a partial archive, fails.
        target.write_bytes(b"PARTIAL-SYNTHETIC-DUMP-B")
        return subprocess.CompletedProcess(cmd, 1, "", "pg_dump: synthetic failure")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_pg_dump)

    with ThreadPoolExecutor(max_workers=1) as pool:
        future_a = pool.submit(svc.create_backup, "manual")
        assert inflight_started.wait(timeout=10), "run A never reached its dump"

        with pytest.raises(Exception):  # noqa: B017 — create_backup raises bare Exception on dump failure
            svc.create_backup("manual")  # run B, synchronous, while A is in flight

        release_inflight.set()
        info_a = future_a.result(timeout=10)

    published = tmp_path / info_a["filename"]
    assert published.exists(), "the in-flight run's archive was never published"
    assert published.read_bytes() == b"SYNTHETIC-DUMP-A", (
        "the failing run deleted or corrupted the in-flight run's artifact"
    )
    assert list(tmp_path.glob("*.tmp")) == [], "temp leftovers after both runs ended"


def test_retention_never_sweeps_in_flight_tmp(tmp_path):
    """PMR-2 family: retention cleanup must neither count nor delete another
    writer's in-flight ``.tmp`` artifact, even when the directory is over the
    max-backups limit (the tmp must not displace published archives from the
    keep-window either)."""
    import os
    import time

    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 2

    base = time.time() - 1000
    for i in range(3):
        p = tmp_path / f"backup_manual_2026010{i + 1}_000000.db"
        p.write_bytes(b"x" * 8)
        stamp = base + i * 100
        os.utime(p, (stamp, stamp))
    inflight = tmp_path / "backup_manual_20261106_120000.9f3ab12c.db.tmp"
    inflight.write_bytes(b"OTHER-WRITER-IN-FLIGHT")
    now = time.time()
    os.utime(inflight, (now, now))  # newest artifact in the directory
    inflight_gz = tmp_path / "backup_manual_20261106_120000.1a2b3c4d.db.gz.tmp"
    inflight_gz.write_bytes(b"OTHER-WRITER-GZ-IN-FLIGHT")
    os.utime(inflight_gz, (now, now))

    svc._cleanup_old_backups()

    assert inflight.exists(), "retention swept another writer's in-flight temp file"
    assert inflight.read_bytes() == b"OTHER-WRITER-IN-FLIGHT"
    assert inflight_gz.exists(), "retention swept another writer's in-flight gz temp file"
    assert inflight_gz.read_bytes() == b"OTHER-WRITER-GZ-IN-FLIGHT"
    remaining = sorted(p.name for p in tmp_path.glob("backup_*.db"))
    assert len(remaining) == 2, (
        f"the in-flight tmp displaced published archives from the keep-window: {remaining}"
    )


# ---------------------------------------------------------------------------
# PMR-3 — post-merge review of #3888 (P1): incomplete gzip archives must
# never be visible under the final ``.db.gz`` name.
# ---------------------------------------------------------------------------


def test_gzip_compression_never_exposes_partial_archive(tmp_path, monkeypatch):
    """PMR-3: while gzip compression is running, the final ``.db.gz`` name
    must not exist — list/retention must never observe a partial archive.
    Compression streams into a single run-private ``.gz.tmp`` and the
    published archive decompresses to the complete dump."""
    svc = _concurrent_svc(tmp_path, monkeypatch)
    monkeypatch.setenv("BACKUP_COMPRESS", "true")

    payload = b"SYNTHETIC-DUMP-FOR-GZIP" * 64

    def fake_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        assert "pg_dump" in str(cmd[0]), f"unexpected subprocess call: {cmd}"
        Path(cmd[list(cmd).index("-f") + 1]).write_bytes(payload)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_pg_dump)

    real_copyfileobj = backup_service_module.shutil.copyfileobj
    snapshot: dict[str, list[str]] = {}

    def spy_copyfileobj(f_in, f_out, *args, **kwargs):
        # Called mid-compression: the final .db.gz must not exist yet.
        snapshot["final_gz"] = [p.name for p in tmp_path.glob("backup_*.db.gz")]
        snapshot["gz_tmp"] = [p.name for p in tmp_path.glob("backup_*.gz.tmp")]
        return real_copyfileobj(f_in, f_out, *args, **kwargs)

    monkeypatch.setattr(backup_service_module.shutil, "copyfileobj", spy_copyfileobj)

    info = svc.create_backup("manual")

    assert info["compressed"] is True
    assert info["filename"].endswith(".db.gz")
    assert snapshot["final_gz"] == [], (
        "partial .db.gz was visible under its final name mid-compression: "
        f"{snapshot['final_gz']}"
    )
    assert len(snapshot["gz_tmp"]) == 1, (
        f"compression did not stream into a single run-private .gz.tmp: {snapshot['gz_tmp']}"
    )
    import gzip as gzip_mod

    assert gzip_mod.decompress((tmp_path / info["filename"]).read_bytes()) == payload, (
        "published archive is not the complete dump"
    )
    assert list(tmp_path.glob("backup_*.gz.tmp")) == [], "gz temp leftover after success"


def test_failed_compression_leaves_no_partial_gz(tmp_path, monkeypatch):
    """PMR-3: a compression failure mid-stream must leave neither a partial
    archive under the final ``.db.gz`` name nor a ``.gz.tmp`` leftover; the
    uncompressed ``.db`` remains the published artifact."""
    svc = _concurrent_svc(tmp_path, monkeypatch)
    monkeypatch.setenv("BACKUP_COMPRESS", "true")

    payload = b"SYNTHETIC-DUMP-FOR-GZIP-FAIL" * 32

    def fake_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        assert "pg_dump" in str(cmd[0]), f"unexpected subprocess call: {cmd}"
        Path(cmd[list(cmd).index("-f") + 1]).write_bytes(payload)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_pg_dump)

    def boom(*args, **kwargs):
        raise OSError("synthetic: disk full mid-compression")

    monkeypatch.setattr(backup_service_module.shutil, "copyfileobj", boom)

    info = svc.create_backup("manual")

    assert info["compressed"] is False, "failed compression must fall back to the .db"
    assert info["filename"].endswith(".db") and not info["filename"].endswith(".gz")
    assert (tmp_path / info["filename"]).read_bytes() == payload, (
        "uncompressed fallback archive is missing or corrupted"
    )
    assert list(tmp_path.glob("backup_*.gz.tmp")) == [], "partial .gz.tmp leftover"
    assert list(tmp_path.glob("backup_*.db.gz")) == [], "partial .db.gz under final name"


# ---------------------------------------------------------------------------
# PMR-4 — post-merge review of #3888 (P2): the per-run id must be reserved
# exclusively; forced identical ids must not share paths or clobber finals.
# ---------------------------------------------------------------------------


class _ScriptedUuidModule:
    """uuid-module stand-in handing out a fixed id sequence (only uuid4 is
    used by backup_service). Thread-safe so concurrent runs can share it."""

    def __init__(self, values: list[str]):
        self._values = values
        self._lock = threading.Lock()
        self._next = 0

    def uuid4(self) -> uuid.UUID:
        with self._lock:
            value = self._values[min(self._next, len(self._values) - 1)]
            self._next += 1
        return uuid.UUID(value)


def test_forced_runid_collision_reserves_unique_temp_paths(tmp_path, monkeypatch):
    """PMR-4: with FORCED identical run ids handed to two concurrent runs,
    exclusive temp creation (O_CREAT|O_EXCL) must make the loser reroll a
    fresh id — the runs never share one temp path and both archives
    publish intact under distinct final names."""
    svc = _concurrent_svc(tmp_path, monkeypatch)

    same_id = "00000000-0000-0000-0000-000000000000"  # hex[:8] == "00000000"
    other_id = "11111111-1111-1111-1111-111111111111"  # hex[:8] == "11111111"
    monkeypatch.setattr(
        backup_service_module, "uuid", _ScriptedUuidModule([same_id, same_id, other_id, other_id])
    )

    dump_barrier = threading.Barrier(2)
    seq_lock = threading.Lock()
    targets: list[Path] = []

    def fake_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        assert "pg_dump" in str(cmd[0]), f"unexpected subprocess call: {cmd}"
        target = Path(cmd[list(cmd).index("-f") + 1])
        with seq_lock:
            seq = len(targets)
            targets.append(target)
        try:
            dump_barrier.wait(timeout=10)
        except threading.BrokenBarrierError:
            pass  # the other run already failed — let this one proceed
        target.write_bytes(f"SYNTHETIC-DUMP-{seq}".encode())
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_pg_dump)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(svc.create_backup, "manual") for _ in range(2)]
        infos = [f.result(timeout=30) for f in futures]

    assert len({str(t) for t in targets}) == 2, (
        f"forced same-id runs shared one temp path: {targets}"
    )
    filenames = [info["filename"] for info in infos]
    assert len(set(filenames)) == 2, f"runs published colliding final names: {filenames}"
    finals = sorted(tmp_path.glob("backup_manual_20261106_120000*.db"))
    assert {p.read_bytes() for p in finals} == {b"SYNTHETIC-DUMP-0", b"SYNTHETIC-DUMP-1"}, (
        "a forced-id collision corrupted or lost an archive"
    )
    assert list(tmp_path.glob("*.tmp")) == [], "temp leftovers after forced-id runs"


def test_publish_never_clobbers_archive_under_forced_runid(tmp_path, monkeypatch):
    """PMR-4: even when an archive already exists under the same identity
    (sequential run reusing a forced identical run id), publication must
    never overwrite it — the new archive is published under an additional
    unique suffix and the earlier archive stays byte-intact."""
    svc = _concurrent_svc(tmp_path, monkeypatch)

    forced = "00000000-0000-0000-0000-000000000000"
    monkeypatch.setattr(backup_service_module, "uuid", _ScriptedUuidModule([forced]))

    calls = {"n": 0}

    def fake_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        assert "pg_dump" in str(cmd[0]), f"unexpected subprocess call: {cmd}"
        calls["n"] += 1
        Path(cmd[list(cmd).index("-f") + 1]).write_bytes(f"SYNTHETIC-DUMP-{calls['n']}".encode())
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_pg_dump)

    first = svc.create_backup("manual")
    second = svc.create_backup("manual")  # same forced run id, later in time

    first_path = tmp_path / first["filename"]
    second_path = tmp_path / second["filename"]

    assert first_path.exists() and second_path.exists(), "an archive was lost"
    assert first["filename"] != second["filename"], (
        f"second run silently reused the first run's final name: {second['filename']}"
    )
    assert first_path.read_bytes() == b"SYNTHETIC-DUMP-1", (
        "the second run overwrote the first run's completed archive"
    )
    assert second_path.read_bytes() == b"SYNTHETIC-DUMP-2"
    assert second["filename"].startswith(first["filename"][:-3]), (
        f"rerolled name lost the original stem: {second['filename']}"
    )
    assert list(tmp_path.glob("*.tmp")) == [], "temp leftovers after forced-id runs"


# ---------------------------------------------------------------------------
# PMR-5 — second-pass review of #3888 (P1): the hardlink-less publish
# fallback must be no-replace; os.replace must never touch this path.
# ---------------------------------------------------------------------------


def test_publish_without_hardlink_support_never_overwrites(tmp_path, monkeypatch):
    """PMR-5: when ``os.link`` is unsupported (FAT, some network shares),
    the fallback publish must still be no-replace. A candidate name that
    collides with an already-completed archive must NOT replace it — the
    pre-fix fallback used ``os.replace`` and destroyed the earlier file."""
    import errno
    import os as os_mod

    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 10
    svc.db = None

    final = tmp_path / "backup_manual_20260101_010101.aaaabbbb.db"
    final.write_bytes(b"OLD-COMPLETED-ARCHIVE")

    candidate = tmp_path / "backup_manual_20260101_010101.aaaabbbb.db.tmp"
    candidate.write_bytes(b"NEW-ARCHIVE-BYTES")

    def no_hardlinks(src, dst):
        raise OSError(errno.EOPNOTSUPP, "synthetic: hard links not supported")

    monkeypatch.setattr(backup_service_module.os, "link", no_hardlinks)

    published = svc._publish_backup(candidate, final.name)

    assert final.exists() and final.read_bytes() == b"OLD-COMPLETED-ARCHIVE", (
        "the hardlink-less fallback overwrote an already-completed archive"
    )
    assert published != final, "fallback claimed the already-taken final name"
    assert published.name.endswith(".db"), (
        f"rerolled name lost the published-format suffix: {published.name}"
    )
    assert published.read_bytes() == b"NEW-ARCHIVE-BYTES", (
        "the new archive was lost or corrupted by the fallback publish"
    )
    assert not os_mod.path.exists(str(candidate)), "candidate temp survived publish"
    assert list(tmp_path.glob("*.tmp")) == [], "temp leftovers after fallback publish"


# ---------------------------------------------------------------------------
# PMR-6 — second-pass review of #3888 (P1): archive file permissions.
# ---------------------------------------------------------------------------


def test_backup_artifacts_are_owner_only(tmp_path, monkeypatch):
    """PMR-6: dumps, run-private temp artifacts and published archives must
    be owner-only (0600) regardless of umask — with umask 022 the pre-fix
    code produced world-readable 0644 backups containing the full database."""
    import os as os_mod

    svc = _concurrent_svc(tmp_path, monkeypatch)

    payload = b"SYNTHETIC-DUMP-PERMISSIONS" * 16

    def fake_pg_dump(cmd, env=None, capture_output=True, text=True, check=False, **kwargs):
        assert "pg_dump" in str(cmd[0]), f"unexpected subprocess call: {cmd}"
        Path(cmd[list(cmd).index("-f") + 1]).write_bytes(payload)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(backup_service_module.subprocess, "run", fake_pg_dump)

    old_umask = os_mod.umask(0o022)  # deterministic world-readable baseline
    try:
        monkeypatch.setenv("BACKUP_COMPRESS", "false")
        plain = svc.create_backup("manual")
        monkeypatch.setenv("BACKUP_COMPRESS", "true")
        gz = svc.create_backup("manual")
    finally:
        os_mod.umask(old_umask)

    plain_path = tmp_path / plain["filename"]
    gz_path = tmp_path / gz["filename"]
    assert plain_path.exists() and gz_path.exists(), "an artifact went missing"
    for artifact, label in ((plain_path, "uncompressed"), (gz_path, "gzip")):
        mode = artifact.stat().st_mode & 0o777
        assert mode == 0o600, (
            f"{label} archive is group/world-readable (mode {oct(mode)}): "
            "backup artifacts must be owner-only 0600"
        )


# ---------------------------------------------------------------------------
# PMR-7 — second-pass review of #3888 (P2): DR-drill discovery must ignore
# in-flight temp artifacts.
# ---------------------------------------------------------------------------


def test_dr_drill_discovery_ignores_in_flight_tmp_artifacts(tmp_path, monkeypatch):
    """PMR-7: ``find_latest_backup`` must select only PUBLISHED archives.
    In-flight ``.db.tmp``/``.db.gz.tmp`` artifacts are typically NEWER than
    the last completed backup; the pre-fix ``glob('backup_*')`` picked the
    partial file and the drill restored garbage / failed spuriously."""
    import gzip as gzip_mod
    import os as os_mod
    import time as time_mod

    monkeypatch.delenv("BACKUP_FILE", raising=False)
    monkeypatch.setattr(dr_drill, "BACKUP_DIR", tmp_path)

    completed = tmp_path / "backup_manual_20260101_000000.aaaabbbb.db.gz"
    completed.write_bytes(gzip_mod.compress(b"COMPLETED-SYNTHETIC-DUMP"))
    inflight_gz = tmp_path / "backup_manual_20260101_000001.ccccdddd.db.gz.tmp"
    inflight_gz.write_bytes(b"PARTIAL-NOT-A-GZIP")
    inflight_db = tmp_path / "backup_manual_20260101_000002.eeeeffff.db.tmp"
    inflight_db.write_bytes(b"PARTIAL-DUMP-IN-FLIGHT")

    old = time_mod.time() - 500
    os_mod.utime(completed, (old, old))
    now = time_mod.time()
    os_mod.utime(inflight_gz, (now, now))
    os_mod.utime(inflight_db, (now, now))

    latest = dr_drill.find_latest_backup()

    assert latest == completed, (
        f"drill selected an in-flight temp artifact: {latest.name}"
    )


# ---------------------------------------------------------------------------
# PMR-8 — second-pass review of #3888 (P2): a gzip publication collision
# must keep the published-format suffix and stay discoverable.
# ---------------------------------------------------------------------------


def test_gzip_collision_publish_stays_discoverable(tmp_path):
    """PMR-8: forcing FileExistsError during ``.db.gz`` publication must
    insert the collision token BEFORE the compound ``.db.gz`` suffix — the
    pre-fix branch produced ``...db.<token>.gz``, a file that the
    ``backup_*.db`` / ``backup_*.db.gz`` allowlists of ``list_backups()``
    and retention can never discover (review-confirmed with Path.glob)."""
    import os as os_mod
    import time as time_mod

    svc = BackupService.__new__(BackupService)
    svc.backup_dir = tmp_path
    svc.retention_days = 7
    svc.max_backups = 1
    svc.db = None

    final_name = "backup_manual_20261106_120000.abc12345.db.gz"
    existing = tmp_path / final_name
    existing.write_bytes(b"EXISTING-COMPLETED-ARCHIVE")
    # Legacy-form file published by the pre-fix collision branch: invisible
    # to the allowlist globs; discovery must tolerate it too.
    legacy = tmp_path / "backup_manual_20261101_000000.abc12345.db.deadbeef.gz"
    legacy.write_bytes(b"LEGACY-FORM-ARCHIVE")

    candidate = tmp_path / (final_name + ".tmp")
    candidate.write_bytes(b"NEW-ARCHIVE-BYTES")

    base = time_mod.time() - 100
    os_mod.utime(existing, (base - 300, base - 300))
    os_mod.utime(legacy, (base - 200, base - 200))
    os_mod.utime(candidate, (base, base))

    published = svc._publish_backup(candidate, final_name)

    assert published != existing, "collision publish claimed the taken name"
    assert existing.read_bytes() == b"EXISTING-COMPLETED-ARCHIVE", (
        "collision publish clobbered the completed archive"
    )
    assert published.name.endswith(".db.gz"), (
        f"collision name fell outside the published-format allowlist: {published.name}"
    )
    assert published.read_bytes() == b"NEW-ARCHIVE-BYTES"

    listed = {entry["filename"] for entry in svc.list_backups()}
    expected = {final_name, published.name, legacy.name}
    assert expected <= listed, (
        f"published archives missing from list_backups(): "
        f"missing={sorted(expected - listed)} listed={sorted(listed)}"
    )

    svc._cleanup_old_backups()  # max_backups=1: keep only the newest

    assert published.exists(), "retention dropped the newest published archive"
    assert not existing.exists() and not legacy.exists(), (
        "retention kept more than max_backups archives"
    )
    assert not candidate.exists() or candidate == published, (
        "the publication candidate temp survived as a leftover"
    )


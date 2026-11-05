"""
Disaster Recovery Drill — restore latest backup into a throwaway DB and smoke-test it.

Why this script exists:
- The clinic has backup_service.py + scheduled_backup.py + BACKUP_RESTORE_PROCEDURES.md.
- None of that proves the backups actually RESTORE. A backup you've never
  restored is a wish, not a backup.
- This script creates a temporary DB, restores the latest backup into it,
  runs a few smoke queries, and reports pass/fail. Run weekly in CI (P2)
  or manually before any deploy that touches migrations.

Usage:
    # From backend/ directory, with venv active
    python -m app.scripts.dr_drill

    # Or as a script
    python backend/app/scripts/dr_drill.py

    # Point at a specific backup file
    BACKUP_FILE=/path/to/backup_2026_07_01.db.gz \\
        python backend/app/scripts/dr_drill.py

Exit codes:
    0 = drill passed
    1 = drill failed (see logs)
    2 = preconditions not met (no backup found, no pg_restore, etc.)

Env vars:
    BACKUP_FILE            — explicit backup path (optional; default: latest in backups/)
    DRILL_DB_NAME          — temp DB name (default: clinic_dr_drill)
    DRILL_DB_DROP_ON_START — '1' to drop existing drill DB before start (default: '1')
    ALLOW_SQLITE_DATABASE_URL — required if backup is SQLite (we force PG for drill)
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.parse
from datetime import datetime, UTC
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s  %(levelname)-7s  %(message)s")
log = logging.getLogger("dr_drill")

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BACKUP_DIR = Path(os.getenv("BACKUP_DIR", "backups"))
DRILL_DB_NAME = os.getenv("DRILL_DB_NAME", "clinic_dr_drill")
DRILL_DB_DROP_ON_START = os.getenv("DRILL_DB_DROP_ON_START", "1") == "1"

# BR-012: the drill target must be a simple SQL identifier — it is
# interpolated into quoted DROP/CREATE statements from an env var.
_DRILL_DB_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _exit(code: int, msg: str) -> None:
    if code == 0:
        log.info("✅ %s", msg)
    else:
        log.error("❌ %s", msg)
    sys.exit(code)


def _run(cmd: list[str], env: dict | None = None, check: bool = True) -> subprocess.CompletedProcess:
    log.debug("run: %s", " ".join(cmd))
    return subprocess.run(cmd, env=env, capture_output=True, text=True, check=check)


# ---------------------------------------------------------------------------
# Steps
# ---------------------------------------------------------------------------

def find_latest_backup() -> Path:
    """Find the newest backup file in BACKUP_DIR."""
    # Truthiness, not presence: CI passes BACKUP_FILE='' when no explicit
    # file is requested — Path('') resolves to '.' and pg_restore then fails
    # with "directory . does not appear to be a valid archive".
    explicit_backup = os.environ.get("BACKUP_FILE", "").strip()
    if explicit_backup:
        p = Path(explicit_backup)
        if not p.exists():
            _exit(2, f"BACKUP_FILE set but not found: {p}")
        return p

    if not BACKUP_DIR.exists():
        _exit(2, f"Backup directory does not exist: {BACKUP_DIR.absolute()}")

    candidates = sorted(
        [p for p in BACKUP_DIR.glob("backup_*") if p.is_file()],
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        _exit(2, f"No backup files found in {BACKUP_DIR.absolute()}")

    log.info("Found %d backup(s); using latest: %s", len(candidates), candidates[0].name)
    return candidates[0]


def parse_source_db_url() -> tuple[str, str, str, int, str]:
    """Return (user, password, host, port, source_db_name) from DATABASE_URL."""
    from app.core.config import settings

    url = str(settings.DATABASE_URL)
    if not url.startswith("postgresql"):
        _exit(2, f"DR drill requires PostgreSQL source. Got: {url[:50]}...")

    parsed = urllib.parse.urlparse(url.replace("postgresql://", "http://").replace("postgresql+psycopg://", "http://"))
    return (
        parsed.username or "postgres",
        parsed.password or "",
        parsed.hostname or "localhost",
        parsed.port or 5432,
        parsed.path.lstrip("/"),
    )


def ensure_pg_tools() -> None:
    if not shutil.which("pg_restore"):
        _exit(2, "pg_restore not found. Install postgresql-client.")
    if not shutil.which("psql"):
        _exit(2, "psql not found. Install postgresql-client.")


def _require_safe_drill_target(source_db_name: str) -> str:
    """BR-012: validate the drill target BEFORE any destructive command.

    The drill runs its psql/pg_restore with the SOURCE credentials, so a
    ``DRILL_DB_NAME`` equal to the source database turns ``DROP
    DATABASE`` into a source-database deletion. Fail closed on the
    identity collision and on any name that is not a simple SQL
    identifier (the historical code interpolated raw env text into
    quoted SQL)."""
    candidate = (DRILL_DB_NAME or "").strip()
    if not _DRILL_DB_NAME_RE.fullmatch(candidate):
        _exit(
            2,
            "DRILL_DB_NAME must be a simple SQL identifier (letters, digits, "
            f"underscore; no quotes/dashes/dots): {candidate!r}",
        )
    if candidate.casefold() == (source_db_name or "").strip().casefold():
        _exit(
            2,
            f"Refusing DR drill: DRILL_DB_NAME ({candidate!r}) matches the "
            f"source database ({source_db_name!r}). Point DRILL_DB_NAME at a "
            "separate scratch database.",
        )
    return candidate


def drop_and_create_drill_db(user: str, password: str, host: str, port: int) -> bool:
    """Provision the drill target; True only after CREATE succeeds.

    BR-013: both psql calls ran with ``check=False`` and ignored the
    exit status — a failed DROP/CREATE silently continued into the
    restore. Every status is now enforced. BR-017: the run owns the
    target only once CREATE has succeeded; the finally-cleanup never
    drops a database this run did not create.
    """
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    if DRILL_DB_DROP_ON_START:
        log.info("Dropping drill DB '%s' if exists...", DRILL_DB_NAME)
        result = _run(
            ["psql", "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{DRILL_DB_NAME}";'],
            env=env,
            check=False,
        )
        if result.returncode != 0:
            _exit(
                1,
                "DROP DATABASE for drill target failed "
                f"(rc={result.returncode}): {(result.stderr or '')[:300]}",
            )

    log.info("Creating fresh drill DB '%s'...", DRILL_DB_NAME)
    result = _run(
        ["psql", "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f'CREATE DATABASE "{DRILL_DB_NAME}";'],
        env=env,
        check=False,
    )
    if result.returncode != 0:
        _exit(
            1,
            "CREATE DATABASE for drill target failed "
            f"(rc={result.returncode}): {(result.stderr or '')[:300]}",
        )
    return True


def restore_backup(backup_path: Path, user: str, password: str, host: str, port: int) -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    actual_path = backup_path
    extracted_tmp: Path | None = None
    try:
        # Decompress if gzipped
        if backup_path.suffix == ".gz":
            log.info("Decompressing %s...", backup_path.name)
            # BR-016: the historical code wrote ``backup_path.with_suffix("")``
            # INSIDE the backup directory — a same-stem archive next to the
            # .gz was truncated and replaced, and a malformed stream left
            # plaintext bytes behind with no cleanup. Extract into a
            # privately created 0600 temp artifact outside the backup
            # directory; the finally below guarantees removal.
            fd, tmp_name = tempfile.mkstemp(
                prefix=f"dr_drill_{backup_path.stem}.", suffix=".dump"
            )
            os.close(fd)
            extracted_tmp = Path(tmp_name)
            extracted_tmp.chmod(0o600)
            with gzip_open(backup_path, "rb") as src, open(extracted_tmp, "wb") as dst:
                shutil.copyfileobj(src, dst)
            actual_path = extracted_tmp

        log.info("Restoring %s → %s...", actual_path.name, DRILL_DB_NAME)
        result = _run(
            [
                "pg_restore",
                "-h", host,
                "-p", str(port),
                "-U", user,
                "-d", DRILL_DB_NAME,
                "--no-owner",
                "--no-privileges",
                "--clean",
                "--if-exists",
                # BR-013: stop at the first error instead of continuing
                # through a partially restored schema.
                "--exit-on-error",
                "--verbose",
                str(actual_path),
            ],
            env=env,
            check=False,
        )

        # BR-013: the process exit status is authoritative. The historical
        # code ignored ``returncode`` and failed only on stderr lines
        # containing 'ERROR:' — a nonzero pg_restore with a differently
        # shaped diagnostic certified a stale database.
        if result.returncode != 0:
            for ln in (result.stderr or "").splitlines()[:20]:
                log.error("pg_restore: %s", ln)
            _exit(1, f"pg_restore failed with exit code {result.returncode}")

        # Defense in depth: pg_restore diagnostics that look like errors
        # still fail the drill even when the process exited 0.
        error_lines = [ln for ln in result.stderr.splitlines() if "ERROR:" in ln.upper()]
        if error_lines:
            for ln in error_lines[:20]:
                log.error("pg_restore: %s", ln)
            _exit(1, f"pg_restore had {len(error_lines)} ERROR lines")

        log.info("Restore completed.")
    finally:
        if extracted_tmp is not None:
            extracted_tmp.unlink(missing_ok=True)


def gzip_open(path: Path, mode: str):
    import gzip
    return gzip.open(path, mode)


def smoke_test_drill_db(user: str, password: str, host: str, port: int) -> None:
    """Run a few smoke queries against the restored DB."""
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    psql = lambda sql: _run(
        ["psql", "-h", host, "-p", str(port), "-U", user, "-d", DRILL_DB_NAME, "-t", "-A", "-c", sql],
        env=env,
        check=True,
    ).stdout.strip()

    log.info("Smoke testing restored DB...")

    # 1. Core tables exist and have rows (or are at least queryable)
    checks = [
        ("SELECT COUNT(*) FROM users;",            "users"),
        ("SELECT COUNT(*) FROM appointments;",     "appointments"),
        ("SELECT COUNT(*) FROM services;",         "services"),
        ("SELECT COUNT(*) FROM audit_logs;",       "audit_logs"),
    ]

    failed = []
    for sql, label in checks:
        try:
            count = psql(sql)
            log.info("  %-15s → %s rows", label, count)
        except Exception as e:
            log.error("  %-15s → FAILED: %s", label, e)
            failed.append(label)

    if failed:
        _exit(1, f"Smoke test failed for tables: {failed}")

    # 2. RBAC sanity: at least one admin should exist
    admin_count = psql("SELECT COUNT(*) FROM users WHERE role = 'Admin' OR role = 'admin';")
    log.info("  admin users     → %s", admin_count)
    if int(admin_count or "0") == 0:
        _exit(1, "No admin user in restored DB — RBAC data integrity broken.")

    log.info("✅ Smoke test passed.")


def cleanup_drill_db(
    user: str,
    password: str,
    host: str,
    port: int,
    *,
    drill_db_created: bool,
) -> None:
    """Drop the drill DB (best-effort) — but ONLY what this run created.

    BR-017: the historical finally-cleanup dropped ``DRILL_DB_NAME``
    unconditionally, so with ``DRILL_DB_DROP_ON_START=0`` and a failed
    CREATE the run could delete a PREEXISTING database it never owned.
    ``DRILL_KEEP_DB=1`` stays the explicit retain opt-out.
    """
    if os.getenv("DRILL_KEEP_DB", "0") == "1":
        log.info("DRILL_KEEP_DB=1 — leaving drill DB '%s' in place for inspection.", DRILL_DB_NAME)
        return

    if not drill_db_created:
        log.info(
            "Drill DB '%s' was not created by this run — skipping cleanup "
            "(BR-017: never drop a database this run does not own).",
            DRILL_DB_NAME,
        )
        return

    env = os.environ.copy()
    env["PGPASSWORD"] = password
    log.info("Cleaning up drill DB '%s'...", DRILL_DB_NAME)
    _run(
        ["psql", "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f'DROP DATABASE IF EXISTS "{DRILL_DB_NAME}";'],
        env=env,
        check=False,
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    log.info("=" * 70)
    log.info("Disaster Recovery Drill — %s", datetime.now(UTC).isoformat())
    log.info("=" * 70)

    ensure_pg_tools()
    backup_path = find_latest_backup()
    user, password, host, port, source_db = parse_source_db_url()

    # BR-012: identity + identifier validation happens BEFORE any psql,
    # DROP, CREATE or pg_restore command is issued.
    global DRILL_DB_NAME
    DRILL_DB_NAME = _require_safe_drill_target(source_db)
    drill_db_created = False

    try:
        drill_db_created = drop_and_create_drill_db(user, password, host, port)
        restore_backup(backup_path, user, password, host, port)
        smoke_test_drill_db(user, password, host, port)
        _exit(0, "DR drill PASSED — backup is restorable.")
    except subprocess.CalledProcessError as e:
        log.error("Command failed: %s", e.cmd)
        log.error("stderr: %s", e.stderr[:500] if e.stderr else "")
        _exit(1, f"DR drill FAILED: {e}")
    finally:
        cleanup_drill_db(user, password, host, port, drill_db_created=drill_db_created)


if __name__ == "__main__":
    # Allow running as `python app/scripts/dr_drill.py` from backend/
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()

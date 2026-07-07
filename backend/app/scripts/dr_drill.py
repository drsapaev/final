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
    if "BACKUP_FILE" in os.environ:
        p = Path(os.environ["BACKUP_FILE"])
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


def drop_and_create_drill_db(user: str, password: str, host: str, port: int) -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    if DRILL_DB_DROP_ON_START:
        log.info("Dropping drill DB '%s' if exists...", DRILL_DB_NAME)
        _run(
            ["psql", "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS \"{DRILL_DB_NAME}\";"],
            env=env,
            check=False,
        )

    log.info("Creating fresh drill DB '%s'...", DRILL_DB_NAME)
    _run(
        ["psql", "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f"CREATE DATABASE \"{DRILL_DB_NAME}\";"],
        env=env,
        check=False,
    )


def restore_backup(backup_path: Path, user: str, password: str, host: str, port: int) -> None:
    env = os.environ.copy()
    env["PGPASSWORD"] = password

    # Decompress if gzipped
    actual_path = backup_path
    if backup_path.suffix == ".gz":
        log.info("Decompressing %s...", backup_path.name)
        actual_path = backup_path.with_suffix("")  # strip .gz
        with gzip_open(backup_path, "rb") as src, open(actual_path, "wb") as dst:
            shutil.copyfileobj(src, dst)

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
            "--verbose",
            str(actual_path),
        ],
        env=env,
        check=False,
    )

    # pg_restore exits non-zero on warnings (e.g. 'relation already exists' on --clean).
    # We treat stderr as the source of truth: only fail if there are ERROR lines.
    error_lines = [ln for ln in result.stderr.splitlines() if "ERROR:" in ln.upper()]
    if error_lines:
        for ln in error_lines[:20]:
            log.error("pg_restore: %s", ln)
        _exit(1, f"pg_restore had {len(error_lines)} ERROR lines")

    log.info("Restore completed.")


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
        ("SELECT COUNT(*) FROM audit_log;",        "audit_log"),
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


def cleanup_drill_db(user: str, password: str, host: str, port: int) -> None:
    """Drop the drill DB (best-effort)."""
    if os.getenv("DRILL_KEEP_DB", "0") == "1":
        log.info("DRILL_KEEP_DB=1 — leaving drill DB '%s' in place for inspection.", DRILL_DB_NAME)
        return

    env = os.environ.copy()
    env["PGPASSWORD"] = password
    log.info("Cleaning up drill DB '%s'...", DRILL_DB_NAME)
    _run(
        ["psql", "-h", host, "-p", str(port), "-U", user, "-d", "postgres", "-c", f"DROP DATABASE IF EXISTS \"{DRILL_DB_NAME}\";"],
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
    user, password, host, port, _source_db = parse_source_db_url()

    try:
        drop_and_create_drill_db(user, password, host, port)
        restore_backup(backup_path, user, password, host, port)
        smoke_test_drill_db(user, password, host, port)
        _exit(0, "DR drill PASSED — backup is restorable.")
    except subprocess.CalledProcessError as e:
        log.error("Command failed: %s", e.cmd)
        log.error("stderr: %s", e.stderr[:500] if e.stderr else "")
        _exit(1, f"DR drill FAILED: {e}")
    finally:
        cleanup_drill_db(user, password, host, port)


if __name__ == "__main__":
    # Allow running as `python app/scripts/dr_drill.py` from backend/
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    main()

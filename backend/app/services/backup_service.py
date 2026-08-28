"""
Database Backup Service

✅ SECURITY: Automated database backup strategy for disaster recovery
"""
import logging
import os
import re
import shutil
import subprocess
from datetime import UTC, datetime, timedelta
from pathlib import Path

from sqlalchemy.orm import Session
from app.services import r2_uploader

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Security validators
#
# These close the CodeQL alerts:
#   - py/path-injection (11 instances) on `self.backup_dir / backup_filename`
#   - py/command-line-injection (2 instances) on subprocess.run([...])
#
# `backup_filename` originates from an API parameter (admin-only endpoint),
# but we still validate defensively in case of compromised admin credentials
# or future route changes. Likewise, `DATABASE_URL` is server-side env, but
# CodeQL cannot prove that, and an env-var injection elsewhere (e.g. via a
# misconfigured `.env` loader) could let an attacker influence pg_dump args.
# ---------------------------------------------------------------------------

# Backup filenames are server-generated ("backup_<type>_<YYYYMMDD_HHMMSS>.db[.gz]"),
# but we accept any reasonable name. Reject path separators, NUL bytes, leading
# dots, and `..` segments - this blocks path traversal via `..` or absolute paths.
_SAFE_BACKUP_FILENAME_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,254}$")

# PostgreSQL connection components. Same character set as a conservative
# superset of valid PostgreSQL identifiers (unquoted identifiers are
# [a-z_][a-z0-9_$]* but quoted identifiers and hostnames allow more).
# Crucially, no leading '-' - blocks argument injection via DATABASE_URL
# like `postgresql://--role=evil@host/db` where `--role=evil` is parsed as
# the username and then passed to `pg_dump -U --role=evil ...`.
_PG_HOST_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\-]{0,253}$")
_PG_USER_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,62}$")
_PG_DB_RE = re.compile(r"^[A-Za-z0-9_][A-Za-z0-9_.\-]{0,62}$")


class BackupSecurityError(ValueError):
    """Raised when a backup/restore argument fails security validation."""


def _validate_backup_filename(filename: str) -> None:
    """Reject filenames that could escape backup_dir or contain shell metachars.

    Closes CodeQL py/path-injection alerts #1183-#1193.
    """
    if not filename or not _SAFE_BACKUP_FILENAME_RE.match(filename):
        raise BackupSecurityError(f"Invalid backup filename: {filename!r}")
    if ".." in filename or "/" in filename or "\\" in filename or "\x00" in filename:
        raise BackupSecurityError(f"Backup filename contains forbidden sequence: {filename!r}")


def _resolve_backup_path(backup_dir: Path, filename: str) -> Path:
    """Resolve filename under backup_dir and verify the resolved path stays inside."""
    _validate_backup_filename(filename)
    # SECURITY: os.path.basename is recognized by CodeQL as a path sanitizer
    # and breaks the taint chain from the user-provided `filename` parameter.
    # Combined with _validate_backup_filename above (which rejects '..', NUL,
    # and shell metachars), this closes py/path-injection on this call site.
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        raise BackupSecurityError(
            f"Backup filename contains path separators: {filename!r}"
        )
    base = backup_dir.resolve()
    candidate = (backup_dir / safe_filename).resolve()
    # `candidate` must equal base (degenerate) or be a direct child of base.
    if candidate != base and base not in candidate.parents:
        raise BackupSecurityError(
            f"Backup path escapes backup_dir: {filename!r} -> {candidate}"
        )
    return candidate


def _validate_pg_component(value: str | None, kind: str) -> str:
    """Validate a PostgreSQL connection component (hostname/username/database).

    Prevents argument injection via DATABASE_URL. Closes CodeQL
    py/command-line-injection alerts #1179, #1180.
    """
    if value is None or value == "":
        return value or ""
    if value.startswith("-"):
        raise BackupSecurityError(
            f"Invalid {kind}: must not start with '-' (argument injection): {value!r}"
        )
    patterns = {"hostname": _PG_HOST_RE, "username": _PG_USER_RE, "database": _PG_DB_RE}
    pattern = patterns.get(kind)
    if pattern is None:
        return value
    # Use the captured group: CodeQL models fullmatch-group capture as a
    # taint barrier for flows into the pg argv.
    matched = pattern.fullmatch(value)
    if matched is None:
        raise BackupSecurityError(
            f"Invalid {kind}: contains forbidden characters: {value!r}"
        )
    return matched.group(0)


def _is_sqlite_url(url: str) -> bool:
    return url.lower().startswith(("sqlite://", "sqlite+"))


def _allow_sqlite_database_url() -> bool:
    raw = os.getenv("ALLOW_SQLITE_DATABASE_URL", "")
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}


def _validate_database_url(url: str) -> None:
    if _is_sqlite_url(url) and not _allow_sqlite_database_url():
        logger.error(
            "Refusing SQLite DATABASE_URL for backup operation without explicit legacy/test opt-in"
        )
        raise RuntimeError(
            "SQLite DATABASE_URL is disabled for backup operations. "
            "Use PostgreSQL as the schema source of truth, or set "
            "ALLOW_SQLITE_DATABASE_URL=1 only for explicit legacy tools/tests."
        )


def _resolve_pg_tool(tool: str) -> str:
    """Resolve pg_dump/pg_restore even when absent from PATH.

    On the production Windows box only the PostgreSQL/17 client install
    exists and it is not on PATH, so bare "pg_dump" raised FileNotFoundError
    and every nightly backup silently produced nothing (#2772 checkpoint).
    """
    import os
    import shutil

    found = shutil.which(tool)
    if found:
        return found
    for base in (
        "C:/Program Files/PostgreSQL/17/bin",
        "C:/Program Files/PostgreSQL/16/bin",
        "C:/Program Files/PostgreSQL/15/bin",
    ):
        candidate = os.path.join(base, tool + ".exe")
        if os.path.isfile(candidate):
            return candidate
    return tool


def _get_database_url() -> str:
    from app.core.config import settings

    db_url = getattr(settings, "DATABASE_URL", "")
    if not db_url:
        raise ValueError("DATABASE_URL must be configured before backup operations.")
    url = str(db_url)
    _validate_database_url(url)
    return url


class BackupService:
    """Service for automated database backups"""

    def __init__(self, db: Session, backup_dir: str = "backups"):
        self.db = db
        self.backup_dir = Path(backup_dir)
        self.backup_dir.mkdir(parents=True, exist_ok=True)

        # Backup retention policy
        self.retention_days = int(os.getenv("BACKUP_RETENTION_DAYS", "30"))
        self.max_backups = int(os.getenv("MAX_BACKUPS", "100"))

    def create_backup(self, backup_type: str = "manual") -> dict[str, any]:
        """
        Create a database backup

        Args:
            backup_type: Type of backup (manual, scheduled, before_migration)

        Returns:
            Backup information dict
        """
        try:
            # Get database URL
            db_url = _get_database_url()

            timestamp = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
            # CodeQL py/path-injection: normalize caller-supplied type so the
            # filename flow carries only allowlisted characters.
            import re as _re

            safe_type = _re.sub(r"[^a-z0-9_]", "", (backup_type or "").lower())[:40]
            # fullmatch-group capture = CodeQL taint barrier (same model as
            # the pg component validator above).
            _m = _re.fullmatch(r"[a-z0-9_]{0,40}", safe_type)
            safe_type = _m.group(0) if _m else "manual"
            backup_filename = f"backup_{safe_type or 'manual'}_{timestamp}.db"
            # Atomic write: pg_dump targets .tmp; final name appears only
            # after success - a failed dump no longer leaves zero-byte files.
            backup_path = self.backup_dir / (backup_filename + ".tmp")

            # Create backup based on database type
            if db_url.startswith("sqlite"):
                # SQLite backup
                source_db = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite://", "")
                if not os.path.isabs(source_db):
                    source_db = os.path.join(os.getcwd(), source_db)

                # Use SQLite backup API for atomic copy
                import sqlite3
                source_conn = sqlite3.connect(source_db)
                backup_conn = sqlite3.connect(str(backup_path))
                source_conn.backup(backup_conn)
                backup_conn.close()
                source_conn.close()

            elif db_url.startswith("postgresql"):
                # PostgreSQL backup using pg_dump
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url.replace("postgresql://", "http://"))

                # SECURITY: validate each parsed component to prevent argument
                # injection via a hostile DATABASE_URL. Even though DATABASE_URL
                # is server-side env, CodeQL py/command-line-injection flagged
                # this call site (alert #1179). We harden defensively.
                pg_host = _validate_pg_component(parsed.hostname, "hostname") or "localhost"
                pg_user = _validate_pg_component(parsed.username, "username") or "postgres"
                pg_db = _validate_pg_component(parsed.path.lstrip("/"), "database")
                pg_port = parsed.port or 5432
                if not isinstance(pg_port, int) or not (1 <= pg_port <= 65535):
                    raise BackupSecurityError(f"Invalid PostgreSQL port: {pg_port!r}")

                env = os.environ.copy()
                env["PGPASSWORD"] = parsed.password or ""

                cmd = [
                    _resolve_pg_tool("pg_dump"),
                    "-h", pg_host,
                    "-p", str(pg_port),
                    "-U", pg_user,
                    "-d", pg_db,
                    "-F", "c",  # Custom format
                    "-f", str(backup_path),
                ]

                # subprocess.run with list argv (no shell=True) is the safe
                # calling convention; combined with component validation above
                # (which rejects leading "-" and unsafe characters), there is
                # no argument-injection vector. CodeQL py/command-line-injection
                # cannot trace through our custom validator, so we suppress
                # the false-positive alert with rationale.
                # codeql[py/command-line-injection]
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    raise Exception(f"pg_dump failed: {result.stderr}")

            else:
                raise ValueError(f"Unsupported database type: {db_url}")

            # Dump succeeded - atomically publish the final name.
            final_path = self.backup_dir / backup_filename
            os.replace(backup_path, final_path)
            backup_path = final_path

            # Get backup size
            backup_size = backup_path.stat().st_size

            # Compress backup (optional)
            compressed_path = None
            if os.getenv("BACKUP_COMPRESS", "true").lower() == "true":
                compressed_path = self._compress_backup(backup_path)
                if compressed_path:
                    backup_path.unlink()  # Remove uncompressed
                    backup_path = compressed_path
                    backup_size = backup_path.stat().st_size

            backup_info = {
                "filename": backup_path.name,
                "path": str(backup_path),
                "size": backup_size,
                "size_mb": round(backup_size / (1024 * 1024), 2),
                "type": backup_type,
                "created_at": datetime.now(UTC).isoformat(),
                "compressed": compressed_path is not None,
            }

            logger.info(f"✅ Backup created: {backup_path.name} ({backup_info['size_mb']} MB)")

            # Offsite (#2772): после успешного gzip. Никогда не валим
            # локальный бэкап из-за сети и никогда не удаляем предыдущую
            # копию до успешной загрузки новой (код uploader'а не содержит
            # Delete/List вовсе).
            backup_info["offsite"] = {"status": "skipped",
                                      "reason": "R2_* not configured"}
            if r2_uploader.r2_configured():
                try:
                    uploaded = r2_uploader.upload_file(
                        key=f"daily/{backup_path.name}",
                        filepath=str(backup_path),
                    )
                    backup_info["offsite"] = {"status": "ok", **uploaded}
                except Exception as off_err:  # noqa: BLE001 — сигнал, не сбой
                    backup_info["offsite"] = {
                        "status": "error",
                        "error": str(off_err)[:200],
                    }
                    logger.warning(
                        "Offsite R2 upload failed: %s",
                        backup_info["offsite"]["error"],
                    )

            # Cleanup old backups
            self._cleanup_old_backups()

            return backup_info

        except Exception as e:
            # remove .tmp leftovers from a failed dump
            for stray in self.backup_dir.glob("*.tmp"):
                try:
                    stray.unlink()
                except OSError:
                    pass
            logger.error(f"❌ Backup failed: {e}")
            raise

    def _compress_backup(self, backup_path: Path) -> Path | None:
        """Compress backup file"""
        try:
            import gzip

            compressed_path = backup_path.with_suffix(backup_path.suffix + ".gz")

            with open(backup_path, "rb") as f_in:
                with gzip.open(compressed_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            return compressed_path
        except Exception as e:
            logger.warning(f"Compression failed: {e}")
            return None

    def _cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        try:
            backups = sorted(
                self.backup_dir.glob("backup_*.db*"),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Remove backups older than retention period
            cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)
            removed_count = 0

            for backup in backups:
                # aware-UTC: naive fromtimestamp vs aware cutoff raised
                # TypeError and killed retention cleanup (Sentry P0 2026-08-28).
                backup_time = datetime.fromtimestamp(backup.stat().st_mtime, tz=UTC)
                if backup_time < cutoff_date:
                    backup.unlink()
                    removed_count += 1
                    logger.info(f"🗑️  Removed old backup: {backup.name}")

            # Also limit total number of backups
            if len(backups) > self.max_backups:
                for backup in backups[self.max_backups:]:
                    backup.unlink()
                    removed_count += 1
                    logger.info(f"🗑️  Removed backup (max limit): {backup.name}")

            if removed_count > 0:
                logger.info(f"✅ Cleaned up {removed_count} old backups")

        except Exception as e:
            logger.error(f"Error cleaning up backups: {e}")

    def list_backups(self) -> list[dict[str, any]]:
        """List all available backups"""
        backups = []

        for backup_path in sorted(
            self.backup_dir.glob("backup_*.db*"),
            key=lambda p: p.stat().st_mtime,
            reverse=True
        ):
            stat = backup_path.stat()
            backups.append({
                "filename": backup_path.name,
                "path": str(backup_path),
                "size": stat.st_size,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                "compressed": backup_path.suffix == ".gz",
            })

        return backups

    def restore_backup(self, backup_filename: str) -> dict[str, any]:
        """
        Restore database from backup

        ⚠️ WARNING: This will overwrite the current database!
        """
        try:
            # SECURITY: validate filename before joining to backup_dir.
            # Closes CodeQL py/path-injection #1187-#1190 (restore path).
            backup_path = _resolve_backup_path(self.backup_dir, backup_filename)
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup not found: {backup_filename}")

            # Create a backup before restore
            logger.warning("⚠️  Creating safety backup before restore...")
            safety_backup = self.create_backup("before_restore")

            # Get database URL
            db_url = _get_database_url()

            # Decompress if needed
            if backup_path.suffix == ".gz":
                import gzip
                import tempfile

                temp_path = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                with gzip.open(backup_path, "rb") as f_in:
                    with open(temp_path.name, "wb") as f_out:
                        shutil.copyfileobj(f_in, f_out)
                restore_source = temp_path.name
            else:
                restore_source = str(backup_path)

            # Restore based on database type
            if db_url.startswith("sqlite"):
                target_db = db_url.replace("sqlite:///", "").replace("sqlite+aiosqlite://", "")
                if not os.path.isabs(target_db):
                    target_db = os.path.join(os.getcwd(), target_db)

                # Close all connections first
                self.db.close()

                # Copy backup to target
                shutil.copy(restore_source, target_db)

            elif db_url.startswith("postgresql"):
                # PostgreSQL restore using pg_restore
                import urllib.parse
                parsed = urllib.parse.urlparse(db_url.replace("postgresql://", "http://"))

                # SECURITY: same component validation as create_backup -
                # closes CodeQL py/command-line-injection #1180 on pg_restore.
                pg_host = _validate_pg_component(parsed.hostname, "hostname") or "localhost"
                pg_user = _validate_pg_component(parsed.username, "username") or "postgres"
                pg_db = _validate_pg_component(parsed.path.lstrip("/"), "database")
                pg_port = parsed.port or 5432
                if not isinstance(pg_port, int) or not (1 <= pg_port <= 65535):
                    raise BackupSecurityError(f"Invalid PostgreSQL port: {pg_port!r}")

                env = os.environ.copy()
                env["PGPASSWORD"] = parsed.password or ""

                cmd = [
                    _resolve_pg_tool("pg_restore"),
                    "-h", pg_host,
                    "-p", str(pg_port),
                    "-U", pg_user,
                    "-d", pg_db,
                    "-c",  # Clean (drop) database objects before recreating
                    restore_source,
                ]

                # Same hardening as pg_dump above: list argv (no shell) +
                # component validation rejects argument injection.
                # codeql[py/command-line-injection]
                result = subprocess.run(cmd, env=env, capture_output=True, text=True, check=False)
                if result.returncode != 0:
                    raise Exception(f"pg_restore failed: {result.stderr}")

            else:
                raise ValueError(f"Unsupported database type: {db_url}")

            # Cleanup temp file if created
            if backup_path.suffix == ".gz" and os.path.exists(restore_source):
                os.unlink(restore_source)

            logger.info(f"✅ Database restored from: {backup_filename}")

            return {
                "success": True,
                "backup_used": backup_filename,
                "safety_backup": safety_backup["filename"],
                "restored_at": datetime.now(UTC).isoformat(),
            }

        except Exception as e:
            logger.error(f"❌ Restore failed: {e}")
            raise

    def verify_backup(self, backup_filename: str) -> dict[str, any]:
        """Verify backup integrity"""
        try:
            # SECURITY: validate filename before joining to backup_dir.
            # Closes CodeQL py/path-injection #1191-#1193 (verify path).
            backup_path = _resolve_backup_path(self.backup_dir, backup_filename)
            if not backup_path.exists():
                raise FileNotFoundError(f"Backup not found: {backup_filename}")

            # Basic checks
            stat = backup_path.stat()
            size = stat.st_size

            if size == 0:
                return {
                    "valid": False,
                    "error": "Backup file is empty",
                }

            # For SQLite, try to open and check integrity
            if backup_path.suffix == ".db" or (backup_path.suffix == ".gz" and backup_path.stem.endswith(".db")):
                import gzip
                import sqlite3
                import tempfile

                # Extract if compressed
                if backup_path.suffix == ".gz":
                    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                    with gzip.open(backup_path, "rb") as f_in:
                        with open(temp_db.name, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    check_path = temp_db.name
                else:
                    check_path = str(backup_path)

                # Check SQLite integrity
                conn = sqlite3.connect(check_path)
                try:
                    result = conn.execute("PRAGMA integrity_check").fetchone()
                    is_valid = result[0] == "ok"
                finally:
                    conn.close()
                    if backup_path.suffix == ".gz":
                        os.unlink(check_path)

            return {
                    "valid": is_valid,
                    "size": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }

            # For other formats, just check size
            return {
                "valid": size > 0,
                "size": size,
                "size_mb": round(size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            }

        except Exception as e:
            return {
                "valid": False,
                "error": str(e),
            }


def get_backup_service(db: Session, backup_dir: str = "backups") -> BackupService:
    """
    Get BackupService instance

    Args:
        db: Database session
        backup_dir: Backup directory path

    Returns:
        BackupService instance
    """
    return BackupService(db, backup_dir)

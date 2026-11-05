"""
Database Backup Service

✅ SECURITY: Automated database backup strategy for disaster recovery
"""
import logging
import os
import re
import secrets
import shutil
import subprocess
import uuid
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
        # BR-018: track this operation's own temp file. Cleanup may remove
        # ONLY this file — a bulk glob("*.tmp") unlink would delete another
        # concurrent writer's in-flight artifact in the shared directory.
        operation_tmp: Path | None = None
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
            # Post-merge review of #3887 (P1 #2): the timestamp has second
            # precision only — two same-type runs started within one second
            # derived the SAME .tmp path and the SAME final name, so one run
            # could delete or replace the other's archive mid-flight.
            # Post-merge review of #3888 (P2): 32 random bits alone are not
            # a uniqueness guarantee either — the temp path is now RESERVED
            # exclusively (O_CREAT|O_EXCL): a same-id competitor cannot even
            # create the file, and this run rerolls a fresh id on collision.
            base_name = f"backup_{safe_type or 'manual'}_{timestamp}"
            backup_path = None
            for _attempt in range(8):
                run_suffix = uuid.uuid4().hex[:8]
                candidate = self.backup_dir / f"{base_name}.{run_suffix}.db.tmp"
                try:
                    # Exclusive reservation: create-and-close an empty file
                    # only this run may own; the dumpers truncate it next.
                    # Second-pass review of #3888 (P1): owner-only from the
                    # first byte — os.open's default 0777&~umask produced
                    # group/world-readable (0755/0644) dumps.
                    fd = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                    os.fchmod(fd, 0o600)  # umask-proof owner-only
                    os.close(fd)
                except FileExistsError:
                    continue
                backup_path = candidate
                break
            if backup_path is None:
                raise RuntimeError(
                    f"Could not reserve a unique backup temp path in "
                    f"{self.backup_dir} after 8 attempts"
                )
            backup_filename = backup_path.name[: -len(".tmp")]
            # Atomic write: pg_dump targets the run-private .tmp; the final
            # name appears only after success - a failed dump no longer
            # leaves zero-byte files.
            operation_tmp = backup_path

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

            # Dump succeeded. The O_EXCL reservation pre-created the temp
            # file, so "pg_dump said ok but wrote nothing" now manifests as a
            # zero-byte reserved file — fail loud instead of publishing it
            # (no zero-byte artifacts under final names, Sentry-P0 rule).
            if backup_path.stat().st_size == 0:
                raise RuntimeError(
                    "pg_dump reported success but produced an empty archive: "
                    f"{backup_path}"
                )
            # Atomically + exclusively publish the final name (#3888 P2):
            # os.link fails with FileExistsError if the name is already
            # taken and this run re-stamps an extra unique suffix — a
            # completed archive is never overwritten.
            final_path = self._publish_backup(backup_path, backup_filename)
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
                    # CodeQL #1283 (py/stack-trace-exposure): в API-ответ
                    # (backup_info → POST /backup/create) уходит только
                    # статический индикатор; детали ошибки R2 (URL/пути
                    # эндпоинта, сетевые тексты) — в лог/Sentry, не наружу.
                    backup_info["offsite"] = {
                        "status": "error",
                        "error": "offsite_upload_failed",
                    }
                    logger.warning(
                        "Offsite R2 upload failed: %s",
                        str(off_err)[:200],
                    )

            # Cleanup old backups
            self._cleanup_old_backups()

            return backup_info

        except Exception as e:
            # BR-018: remove only this operation's temp file. A bulk
            # glob("*.tmp") unlink could delete another concurrent writer's
            # in-flight artifact in the shared backup directory.
            if operation_tmp is not None:
                try:
                    operation_tmp.unlink(missing_ok=True)
                except OSError:
                    pass
            logger.error(f"❌ Backup failed: {e}")
            raise

    def _publish_backup(self, tmp_path: Path, final_name: str) -> Path:
        """Atomically and exclusively publish a completed artifact.

        Post-merge review of #3888 (P2): publication must never overwrite a
        completed archive. ``os.link`` fails with FileExistsError when the
        name is already taken — this run then re-stamps an extra unique
        suffix. Second-pass review of #3888 (P1): on filesystems without
        hard links the fallback must ALSO be no-replace — an exclusive
        create of the final name plus a streamed, fsynced copy with
        rollback. ``os.replace`` is never used on this safety-critical
        path: it silently destroys an already-completed archive when the
        candidate name is taken. The final name appears only with full
        content or not at all.
        """
        final_path = self.backup_dir / final_name
        for _attempt in range(8):
            try:
                os.link(tmp_path, final_path)
            except FileExistsError:
                final_path = self.backup_dir / self._collision_name(final_name)
                continue
            except OSError as link_err:
                # Filesystems without hard links (FAT, some network
                # shares): fall back to the genuinely no-replace publish
                # (exclusive create + copy + fsync + rollback). NEVER
                # os.replace here — a repeated candidate name would
                # replace an already-completed archive.
                logger.warning(
                    "os.link publish unsupported (%s); using no-replace "
                    "exclusive-create fallback for %s",
                    link_err,
                    final_path.name,
                )
                published = self._publish_without_hardlink(tmp_path, final_path)
                if published is not None:
                    return published
                # Name was claimed inside the race window — re-stamp.
                final_path = self.backup_dir / self._collision_name(final_name)
                continue
            tmp_path.unlink(missing_ok=True)
            return final_path
        raise RuntimeError(
            f"Could not publish backup {final_name!r}: final-name collision "
            "persisted after 8 attempts"
        )

    @staticmethod
    def _collision_name(final_name: str) -> str:
        """Fresh token that keeps the published-format suffix.

        Second-pass review of #3888 (P2): ``Path('x.abc12345.db.gz').stem``
        is ``x.abc12345.db``, so ``f"{stem}.{token}{suffix}"`` produced
        ``x.abc12345.db.<token>.gz`` — a name the list/retention allowlist
        (``backup_*.db``, ``backup_*.db.gz``) can never discover. The
        token goes BEFORE the compound ``.db.gz`` suffix instead, so every
        generated name still ends in the published format.
        """
        if final_name.endswith(".db.gz"):
            return f"{final_name[: -len('.db.gz')]}.{secrets.token_hex(3)}.db.gz"
        final = Path(final_name)
        return f"{final.stem}.{secrets.token_hex(3)}{final.suffix}"

    def _publish_without_hardlink(self, tmp_path: Path, final_path: Path) -> Path | None:
        """No-replace publish for filesystems without hard links.

        Second-pass review of #3888 (P1): reserves the final name
        exclusively (``O_CREAT|O_EXCL``, owner-only), streams the bytes
        over, fsyncs and rolls the reservation back on any failure, so a
        partial artifact never survives under the final name. Returns
        ``None`` when the name was claimed by a concurrent writer (the
        caller re-stamps and retries) — it NEVER replaces an existing
        file.
        """
        try:
            fd = os.open(final_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError:
            return None
        except OSError as open_err:
            raise RuntimeError(
                f"Could not publish backup {final_path.name!r}: no no-replace "
                f"publish available (link failed, exclusive create failed: "
                f"{open_err}); refusing to overwrite existing archives"
            ) from open_err
        try:
            with os.fdopen(fd, "wb") as f_out:
                with open(tmp_path, "rb") as f_in:
                    shutil.copyfileobj(f_in, f_out)
                f_out.flush()
                os.fsync(f_out.fileno())
            os.chmod(final_path, 0o600)
        except BaseException:
            # Roll the reservation back: no partial file under the final
            # name — the next attempt (or run) must find the name free.
            try:
                os.unlink(final_path)
            except OSError:
                pass
            raise
        tmp_path.unlink(missing_ok=True)
        return final_path

    def _compress_backup(self, backup_path: Path) -> Path | None:
        """Compress backup file.

        BR-022 (from #3890) + post-merge review of #3888 (P1): compression
        must never leave a partial, published-looking ``.db.gz`` behind and
        must never overwrite a completed archive. The archive is written to
        this operation's private ``.gz.tmp`` file, validated, then published
        atomically AND exclusively — a partial archive is never visible
        under the final name, and a name collision re-stamps an extra
        unique suffix instead of clobbering. On failure only that temp file
        is removed and the caller keeps the good uncompressed source.
        """
        import gzip

        compressed_path = backup_path.with_suffix(backup_path.suffix + ".gz")
        if compressed_path.exists():
            logger.error("Refusing to overwrite an existing archive: %s", compressed_path.name)
            return None

        temp_gz: Path | None = self.backup_dir / (compressed_path.name + ".tmp")
        try:
            # Second-pass review of #3888 (P1): owner-only from the first
            # byte — gzip.open created the temp with 0666&~umask. The path
            # embeds this run's own uuid-suffixed source name, so an
            # existing file is a stale crash leftover, never a live
            # writer: refuse to touch it and keep the uncompressed .db.
            try:
                fd = os.open(temp_gz, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError:
                logger.error("Refusing to reuse existing gz temp: %s", temp_gz.name)
                return None
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "wb") as raw_out:
                with open(backup_path, "rb") as f_in, gzip.open(raw_out, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            if temp_gz.stat().st_size == 0:
                raise OSError("compressed output is empty")
        except Exception as e:
            logger.warning(f"Compression failed: {e}")
            try:
                temp_gz.unlink(missing_ok=True)
            except OSError:
                pass
            return None

        try:
            # Atomic + exclusive publish: no partial archive ever appears
            # under the final name, no completed archive is clobbered.
            return self._publish_backup(temp_gz, compressed_path.name)
        except BaseException:
            try:
                temp_gz.unlink(missing_ok=True)
            except OSError:
                pass
            raise

    def _cleanup_old_backups(self):
        """Remove old backups based on retention policy"""
        try:
            # Post-merge review of #3887 (P1 #2): retention must consider
            # only PUBLISHED archives. The old ``backup_*.db*`` pattern also
            # matched ``*.db.tmp`` artifacts of runs that were still dumping,
            # so an over-limit directory swept another writer's in-flight
            # temp file — and the tmp counted toward the keep-window,
            # displacing published archives. .tmp files belong to their
            # writers and are never touched here.
            backups = sorted(
                {
                    p
                    for pattern in (
                        "backup_*.db",
                        "backup_*.db.gz",
                        "backup_*.db.*.gz",
                    )
                    for p in self.backup_dir.glob(pattern)
                },
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )

            # Remove backups older than retention period
            cutoff_date = datetime.now(UTC) - timedelta(days=self.retention_days)
            removed_count = 0
            removed_paths: set[Path] = set()

            for backup in backups:
                # aware-UTC: naive fromtimestamp vs aware cutoff raised
                # TypeError and killed retention cleanup (Sentry P0 2026-08-28).
                backup_time = datetime.fromtimestamp(backup.stat().st_mtime, tz=UTC)
                if backup_time < cutoff_date:
                    backup.unlink()
                    removed_paths.add(backup)
                    removed_count += 1
                    logger.info(f"🗑️  Removed old backup: {backup.name}")

            # Also limit total number of backups — survivors only (BR-021:
            # the pre-cleanup snapshot re-unlinked an already-removed expired
            # archive, raising FileNotFoundError and logging a misleading
            # retention error while the outcome was actually correct).
            survivors = [b for b in backups if b not in removed_paths]
            if len(survivors) > self.max_backups:
                for backup in survivors[self.max_backups:]:
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

        # Same P1 #2 family as retention: never present another writer's
        # in-flight ``*.tmp`` as a restorable backup.
        # Second-pass review of #3888 (P2): every published generated name
        # must be discoverable — collision re-stamps keep the compound
        # ``.db.gz`` suffix, and the legacy ``...db.<token>.gz`` form is
        # tolerated. Dedupe: ``backup_*.db.gz`` and ``backup_*.db.*.gz``
        # overlap; a duplicated path would be swept twice by retention
        # (the BR-021 double-unlink failure mode).
        for backup_path in sorted(
            {
                p
                for pattern in (
                    "backup_*.db",
                    "backup_*.db.gz",
                    "backup_*.db.*.gz",
                )
                for p in self.backup_dir.glob(pattern)
            },
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
                    "--if-exists",
                    # BR-020: --single-transaction wraps the whole restore
                    # (including the -c drops) in one all-or-nothing
                    # transaction (implies --exit-on-error), so a mid-restore
                    # failure no longer leaves partly committed DDL. The
                    # broader maintenance-gate/isolated-target protocol stays
                    # an operator policy decision tracked in the ledger.
                    "--single-transaction",
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

            # BR-019: route by what the archive actually is, not by its
            # filename — this service writes PostgreSQL custom-format dumps
            # (pg_dump -F c) under a .db[.gz] name, and the historical code
            # fed every such file to SQLite's integrity_check, reporting a
            # restorable PG dump as {"valid": false, "file is not a
            # database"}. SQLite is tried first (no external tool); a
            # non-SQLite file falls through to pg_restore --list; anything
            # neither can read is invalid — the historical "valid: size > 0"
            # fallback is gone.
            is_gz = backup_path.suffix == ".gz"
            check_path = str(backup_path)
            temp_db = None
            try:
                if is_gz:
                    import gzip
                    import tempfile

                    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
                    with gzip.open(backup_path, "rb") as f_in:
                        with open(temp_db.name, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)
                    check_path = temp_db.name

                import sqlite3

                try:
                    conn = sqlite3.connect(check_path)
                    try:
                        integrity = conn.execute("PRAGMA integrity_check").fetchone()[0]
                    finally:
                        conn.close()
                    return {
                        "valid": integrity == "ok",
                        **({} if integrity == "ok" else {"error": f"SQLite integrity check failed: {integrity}"}),
                        "format": "sqlite",
                        "verify_mode": "sqlite PRAGMA integrity_check",
                        "size": size,
                        "size_mb": round(size / (1024 * 1024), 2),
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                except sqlite3.DatabaseError:
                    pass  # not a SQLite database — try the PostgreSQL path

                list_result = subprocess.run(
                    [_resolve_pg_tool("pg_restore"), "-l", check_path],
                    capture_output=True, text=True, check=False,
                )
                if list_result.returncode == 0:
                    return {
                        "valid": True,
                        "format": "postgresql-custom",
                        "verify_mode": "pg_restore --list (archive readable; not a full restore proof)",
                        "size": size,
                        "size_mb": round(size / (1024 * 1024), 2),
                        "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    }
                return {
                    "valid": False,
                    "error": (
                        "unknown archive format (not SQLite; pg_restore --list "
                        f"failed with exit {list_result.returncode}: "
                        f"{(list_result.stderr or list_result.stdout or '')[:200]})"
                    ),
                    "size": size,
                    "size_mb": round(size / (1024 * 1024), 2),
                    "created_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                }
            finally:
                if temp_db is not None:
                    os.unlink(temp_db.name)

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

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import tempfile
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from clinic_lifecycle_common import (
    DatabaseTarget,
    backend_dir,
    fail,
    load_clinic_env,
    parse_database_url,
    pass_message,
    postgres_tool,
    run_command,
)


def _redact_database_url(database_url: str) -> str:
    parsed = urlsplit(database_url)
    if not parsed.password:
        return database_url

    username = parsed.username or ""
    hostname = parsed.hostname or ""
    host = hostname
    if ":" in hostname and not hostname.startswith("["):
        host = f"[{hostname}]"
    if parsed.port:
        host = f"{host}:{parsed.port}"

    netloc = f"{username}:***@{host}" if username else host
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def _is_same_database_target(left: DatabaseTarget, right: DatabaseTarget) -> bool:
    return (
        left.host.lower(),
        left.port,
        left.name,
    ) == (
        right.host.lower(),
        right.port,
        right.name,
    )


def _require_live_restore_confirmation(*, target_database_url: str) -> None:
    runtime_database_url = os.environ.get("DATABASE_URL")
    if runtime_database_url:
        runtime_target = parse_database_url(runtime_database_url)
        restore_target = parse_database_url(target_database_url)
        if not _is_same_database_target(runtime_target, restore_target):
            return
    if os.environ.get("CONFIRM_RESTORE_DB") == "1":
        return
    fail(
        "Refusing to restore into DATABASE_URL without explicit confirmation. "
        "Set RESTORE_DATABASE_URL to a separate rehearsal target, or set "
        "CONFIRM_RESTORE_DB=1 only for an intentional live database restore."
    )


def _prepare_restore_source(backup_file: Path) -> Path:
    if backup_file.suffix != ".gz":
        return backup_file

    # BR-007 (backup/restore source review, PR #3882): the expanded
    # archive is an UNENCRYPTED SQL dump in the shared OS temp
    # directory. The helper owns its cleanup so a malformed or
    # truncated archive can no longer leak the temp file — even when
    # called outside a guarded block (the historical gap: the helper
    # ran before main()'s try/finally).
    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=backup_file.stem)
    temp_file.close()
    temp_path = Path(temp_file.name)
    try:
        # restrictive permissions regardless of platform umask; the
        # plaintext artifact must be operator-only while it exists
        temp_path.chmod(0o600)
        with gzip.open(backup_file, "rb") as source, open(temp_path, "wb") as target:
            shutil.copyfileobj(source, target)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise
    return temp_path


def main() -> int:
    parser = argparse.ArgumentParser(description="Restore a PostgreSQL backup into a clinic database")
    parser.add_argument("--backup-file", default=os.environ.get("BACKUP_FILE") or os.environ.get("RESTORE_BACKUP_FILE"))
    parser.add_argument("--target-database-url", default=os.environ.get("RESTORE_DATABASE_URL") or os.environ.get("DATABASE_URL"))
    args = parser.parse_args()

    load_clinic_env()

    backup_file_value = args.backup_file
    if not backup_file_value:
        fail("BACKUP_FILE or RESTORE_BACKUP_FILE is required")

    backup_file = Path(backup_file_value).expanduser().resolve()
    if not backup_file.exists():
        fail(f"Backup file not found: {backup_file}")

    target_url = args.target_database_url
    if not target_url:
        fail("RESTORE_DATABASE_URL (or DATABASE_URL) is required")

    _require_live_restore_confirmation(target_database_url=target_url)

    target = parse_database_url(target_url)

    # BR-007: the .gz expansion lives INSIDE the guarded block — a
    # decompression failure must release everything it created.
    restore_source = backup_file
    try:
        restore_source = _prepare_restore_source(backup_file)
        suffix = "".join(backup_file.suffixes)
        if suffix.endswith(".sql") or suffix.endswith(".sql.gz"):
            cmd = [
                postgres_tool("psql"),
                # BR-001 (backup/restore source review, PR #3882): psql
                # keeps executing statements after a SQL error and can
                # exit 0 by default, so a failed restore still printed
                # the success marker. -X skips psqlrc, ON_ERROR_STOP=1
                # stops at the first error and fails the command.
                # Transaction wrapping (-1) is deliberately deferred to
                # the BR-011 transactional-restore fix.
                "-X",
                "-v",
                "ON_ERROR_STOP=1",
                "-h",
                target.host,
                "-p",
                str(target.port),
                "-U",
                target.user or "postgres",
                "-d",
                target.name,
                "-f",
                str(restore_source),
            ]
        else:
            cmd = [
                postgres_tool("pg_restore"),
                "-h",
                target.host,
                "-p",
                str(target.port),
                "-U",
                target.user or "postgres",
                "-d",
                target.name,
                "-c",
                "--if-exists",
                str(restore_source),
            ]

        env = os.environ.copy()
        env["PGPASSWORD"] = target.password
        run_command(cmd, env=env, cwd=backend_dir())
    finally:
        if restore_source != backup_file and restore_source.exists():
            restore_source.unlink(missing_ok=True)

    print(f"RESTORED_BACKUP_FILE={backup_file}", flush=True)
    print(f"RESTORE_DATABASE_URL={_redact_database_url(target_url)}", flush=True)
    pass_message(f"restore_db restored {backup_file} into {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

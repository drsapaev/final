#!/usr/bin/env python3
from __future__ import annotations

import argparse
import gzip
import os
import shutil
import tempfile
from pathlib import Path

from clinic_lifecycle_common import (
    backend_dir,
    fail,
    load_clinic_env,
    parse_database_url,
    pass_message,
    postgres_tool,
    run_command,
)


def _prepare_restore_source(backup_file: Path) -> Path:
    if backup_file.suffix != ".gz":
        return backup_file

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=backup_file.stem)
    temp_file.close()
    with gzip.open(backup_file, "rb") as source, open(temp_file.name, "wb") as target:
        shutil.copyfileobj(source, target)
    return Path(temp_file.name)


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

    target = parse_database_url(target_url)
    restore_source = _prepare_restore_source(backup_file)

    try:
        suffix = "".join(backup_file.suffixes)
        if suffix.endswith(".sql") or suffix.endswith(".sql.gz"):
            cmd = [
                postgres_tool("psql"),
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
    print(f"RESTORE_DATABASE_URL={target_url}", flush=True)
    pass_message(f"restore_db restored {backup_file} into {target.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from datetime import datetime
from pathlib import Path

from clinic_lifecycle_common import (
    app_root,
    backend_dir,
    backend_env_file,
    fail,
    load_clinic_env,
    parse_database_url,
    pass_message,
    require_env,
    run_command,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Create a PostgreSQL backup for a clinic deployment")
    parser.add_argument("--backup-dir", default=os.environ.get("BACKUP_DIR"))
    parser.add_argument("--backup-file", default=os.environ.get("BACKUP_FILE"))
    args = parser.parse_args()

    load_clinic_env()

    database_url = require_env("DATABASE_URL")
    target = parse_database_url(database_url)

    backup_dir = Path(args.backup_dir or (app_root() / "output" / "backups"))
    backup_dir.mkdir(parents=True, exist_ok=True)

    if args.backup_file:
        backup_file = Path(args.backup_file)
        backup_file.parent.mkdir(parents=True, exist_ok=True)
    else:
        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_file = backup_dir / f"{target.name}_{timestamp}.dump"

    cmd = [
        "pg_dump",
        "-h",
        target.host,
        "-p",
        str(target.port),
        "-U",
        target.user or "postgres",
        "-d",
        target.name,
        "-F",
        "c",
        "-f",
        str(backup_file),
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = target.password
    run_command(cmd, env=env, cwd=backend_dir())

    if not backup_file.exists() or backup_file.stat().st_size == 0:
        fail(f"Backup was not created or is empty: {backup_file}")

    print(f"BACKUP_FILE={backup_file}", flush=True)
    pass_message(f"backup_db created {backup_file}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

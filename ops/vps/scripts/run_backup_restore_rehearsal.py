#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

from clinic_lifecycle_common import (
    app_root,
    fail,
    load_clinic_env,
    pass_message,
    run_command,
)


def _script(name: str) -> Path:
    return Path(__file__).resolve().parent / name


def _extract_value(stdout: str, key: str) -> str | None:
    prefix = f"{key}="
    for line in stdout.splitlines():
        if line.startswith(prefix):
            return line[len(prefix) :].strip()
    return None


def _invoke(script_name: str, *, extra_env: dict[str, str] | None = None) -> str:
    env = os.environ.copy()
    if extra_env:
        env.update(extra_env)
    result = run_command([sys.executable, str(_script(script_name))], cwd=app_root(), env=env)
    return result.stdout


def main() -> int:
    load_clinic_env()

    restore_database_url = os.environ.get("RESTORE_DATABASE_URL")
    if not restore_database_url:
        fail("RESTORE_DATABASE_URL is required")

    restore_backend_url = os.environ.get("RESTORE_BACKEND_URL")
    restore_public_url = os.environ.get("RESTORE_PUBLIC_URL")
    if not restore_backend_url or not restore_public_url:
        fail("RESTORE_BACKEND_URL and RESTORE_PUBLIC_URL are required for restore smoke")

    backup_dir = os.environ.get("BACKUP_DIR")

    backup_stdout = _invoke(
        "backup_db.py",
        extra_env={"BACKUP_DIR": backup_dir} if backup_dir else None,
    )
    backup_file = _extract_value(backup_stdout, "BACKUP_FILE")
    if not backup_file:
        fail("backup_db did not report BACKUP_FILE")

    if os.environ.get("DATABASE_URL") and os.environ["DATABASE_URL"] == restore_database_url:
        fail("RESTORE_DATABASE_URL must point at a separate target database")

    _invoke(
        "restore_db.py",
        extra_env={
            "BACKUP_FILE": backup_file,
            "RESTORE_DATABASE_URL": restore_database_url,
        },
    )
    _invoke(
        "health_check.py",
        extra_env={
            "BACKEND_URL": restore_backend_url,
            "PUBLIC_URL": restore_public_url,
            "EXPECTED_SETUP_INITIALIZED": "1",
        },
    )
    _invoke(
        "smoke_post_update.py",
        extra_env={
            "BACKEND_URL": restore_backend_url,
            "PUBLIC_URL": restore_public_url,
            "EXPECTED_SETUP_INITIALIZED": "1",
            "SMOKE_REQUIRE_LOGIN": os.environ.get("SMOKE_REQUIRE_LOGIN", "1"),
        },
    )

    print(f"RESTORE_BACKUP_FILE={backup_file}", flush=True)
    print(f"RESTORE_DATABASE_URL={restore_database_url}", flush=True)
    print(f"RESTORE_BACKEND_URL={restore_backend_url}", flush=True)
    print(f"RESTORE_PUBLIC_URL={restore_public_url}", flush=True)
    pass_message("run_backup_restore_rehearsal completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

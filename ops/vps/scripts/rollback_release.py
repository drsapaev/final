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


def main() -> int:
    load_clinic_env()

    rollback_ref = os.environ.get("ROLLBACK_REF")
    if not rollback_ref:
        fail("ROLLBACK_REF is required")

    run_command(["git", "checkout", "--force", rollback_ref], cwd=app_root())

    deploy_script = Path(__file__).resolve().parent / "deploy_release.py"
    run_command([sys.executable, str(deploy_script)], cwd=app_root())

    if os.environ.get("ROLLBACK_RUN_MIGRATIONS", "0").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }:
        migrations_script = Path(__file__).resolve().parent / "run_migrations.py"
        run_command([sys.executable, str(migrations_script)], cwd=app_root())

    # BR-009: this script rolls back CODE (git checkout + redeploy, plus an
    # optional alembic UPGRADE). It never reverts the database schema, so the
    # verdict must not read as a full restore. An old release running against
    # a newer schema stays possible until the operator restores the
    # pre-update backup via the documented manual protocol.
    pass_message(
        f"rollback_release checked out {rollback_ref} (code rollback only; database schema not reverted)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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

    if os.environ.get("ROLLBACK_RUN_MIGRATIONS", "0").strip().lower() in {"1", "true", "yes", "on"}:
        migrations_script = Path(__file__).resolve().parent / "run_migrations.py"
        run_command([sys.executable, str(migrations_script)], cwd=app_root())

    pass_message(f"rollback_release restored {rollback_ref}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

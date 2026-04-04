#!/usr/bin/env python3
from __future__ import annotations

import os
from pathlib import Path

from clinic_lifecycle_common import (
    app_root,
    backend_dir,
    fail,
    load_clinic_env,
    pass_message,
    run_command,
)


def main() -> int:
    load_clinic_env()

    release_ref = os.environ.get("RELEASE_REF")
    if release_ref:
        run_command(["git", "checkout", "--force", release_ref], cwd=app_root())

    deploy_script = Path(__file__).resolve().parent / "deploy_host.sh"
    if not deploy_script.exists():
        fail(f"deploy host script not found: {deploy_script}")

    env = os.environ.copy()
    env["SKIP_MIGRATIONS"] = "1"
    run_command(["bash", str(deploy_script)], cwd=app_root(), env=env)
    pass_message("deploy_release completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from clinic_lifecycle_common import (
    LifecycleError,
    app_root,
    backend_url,
    fail,
    git_head,
    http_json,
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


def _wait_for_backend_ready(*, timeout_seconds: int = 120, interval_seconds: int = 5) -> None:
    deadline = time.monotonic() + timeout_seconds
    health_url = f"{backend_url()}/api/v1/health"
    last_error: str | None = None

    while time.monotonic() < deadline:
        try:
            status, payload, raw = http_json("GET", health_url, timeout=10)
            if status == 200 and isinstance(payload, dict):
                health_ok = payload.get("status") in {"ok", "healthy", True} or payload.get("ok") is True
                if health_ok:
                    return
                last_error = f"unexpected health payload: {payload}"
            else:
                last_error = f"HTTP {status} {raw}"
        except LifecycleError as exc:
            last_error = str(exc)
        time.sleep(interval_seconds)

    fail(
        "Backend did not become ready after deploy within "
        f"{timeout_seconds}s. Last error: {last_error or 'unknown'}"
    )


def main() -> int:
    load_clinic_env()

    update_ref = os.environ.get("UPDATE_RELEASE_REF")
    if not update_ref:
        fail("UPDATE_RELEASE_REF is required")

    rollback_ref = os.environ.get("ROLLBACK_REF") or git_head(app_root())
    baseline_ref = git_head(app_root())
    backup_dir = os.environ.get("BACKUP_DIR")

    try:
        backup_stdout = _invoke(
            "backup_db.py",
            extra_env={"BACKUP_DIR": backup_dir} if backup_dir else None,
        )
        backup_file = _extract_value(backup_stdout, "BACKUP_FILE")
        if not backup_file:
            fail("backup_db did not report BACKUP_FILE")

        _invoke("deploy_release.py", extra_env={"RELEASE_REF": update_ref})
        _invoke("run_migrations.py")
        _wait_for_backend_ready()
        _invoke("health_check.py", extra_env={"EXPECTED_SETUP_INITIALIZED": "1"})
        _invoke("smoke_post_update.py", extra_env={"SMOKE_REQUIRE_LOGIN": os.environ.get("SMOKE_REQUIRE_LOGIN", "1")})
    except Exception as exc:
        rollback_extra = {"ROLLBACK_REF": rollback_ref}
        if os.environ.get("ROLLBACK_RUN_MIGRATIONS"):
            rollback_extra["ROLLBACK_RUN_MIGRATIONS"] = os.environ["ROLLBACK_RUN_MIGRATIONS"]
        try:
            _invoke("rollback_release.py", extra_env=rollback_extra)
        except Exception as rollback_exc:
            fail(
                f"Update rehearsal failed: {exc}. "
                f"Rollback to {rollback_ref} also failed: {rollback_exc}"
            )
        fail(f"Update rehearsal failed and was rolled back to {rollback_ref}: {exc}")

    print(f"UPDATE_BASELINE_REF={baseline_ref}", flush=True)
    print(f"UPDATE_RELEASE_REF={update_ref}", flush=True)
    print(f"UPDATE_ROLLBACK_REF={rollback_ref}", flush=True)
    print(f"UPDATE_BACKUP_FILE={backup_file}", flush=True)
    pass_message("run_update_rehearsal completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

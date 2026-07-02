#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from clinic_lifecycle_common import (
    app_root,
    env_bool,
    fail,
    frontend_runtime_probe_script,
    load_clinic_env,
    pass_message,
    run_command,
)


SENSITIVE_KEYS = {
    "access_token",
    "activation_key",
    "authorization",
    "password",
    "refresh_token",
    "secret",
    "token",
}


def _redact_sensitive(value: Any) -> Any:
    if isinstance(value, dict):
        redacted = {}
        for key, item in value.items():
            if str(key).lower() in SENSITIVE_KEYS:
                redacted[key] = "***"
            else:
                redacted[key] = _redact_sensitive(item)
        return redacted
    if isinstance(value, list):
        return [_redact_sensitive(item) for item in value]
    return value


def _safe_payload(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return _redact_sensitive(value)
    return value


def _run_health_check(expected_initialized: bool) -> None:
    helper = Path(__file__).resolve().parent / "health_check.py"
    env = os.environ.copy()
    env["EXPECTED_SETUP_INITIALIZED"] = "1" if expected_initialized else "0"
    run_command([sys.executable, str(helper)], cwd=app_root(), env=env)


def _run_frontend_runtime_probe() -> None:
    probe_script = frontend_runtime_probe_script()
    if not probe_script.exists():
        fail(f"Missing frontend runtime probe script: {probe_script}")
    run_command(["node", str(probe_script)], cwd=app_root())


def _maybe_login() -> None:
    require_login = env_bool(
        "SMOKE_REQUIRE_LOGIN",
        default=bool(
            os.environ.get("SMOKE_LOGIN_USERNAME")
            or os.environ.get("SMOKE_LOGIN_PASSWORD")
            or os.environ.get("SETUP_ADMIN_USERNAME")
            or os.environ.get("SETUP_ADMIN_PASSWORD")
        ),
    )
    if not require_login:
        return

    username = (
        os.environ.get("SMOKE_LOGIN_USERNAME")
        or os.environ.get("SETUP_ADMIN_USERNAME")
        or os.environ.get("ADMIN_USERNAME")
    )
    password = (
        os.environ.get("SMOKE_LOGIN_PASSWORD")
        or os.environ.get("SETUP_ADMIN_PASSWORD")
        or os.environ.get("ADMIN_PASSWORD")
    )
    if not username or not password:
        fail(
            "Login smoke requested but username/password are missing. "
            "Set SMOKE_LOGIN_USERNAME/SMOKE_LOGIN_PASSWORD or SETUP_ADMIN_*."
        )

    from clinic_lifecycle_common import backend_url, http_json

    status, payload, raw = http_json(
        "POST",
        f"{backend_url()}/api/v1/auth/minimal-login",
        payload={"username": username, "password": password, "remember_me": False},
    )
    if status != 200 or not isinstance(payload, dict):
        fail(f"Login smoke failed: HTTP {status} {_safe_payload(payload or raw)}")
    if not payload.get("access_token"):
        fail(f"Login smoke returned no access token: {_safe_payload(payload)}")


def main() -> int:
    load_clinic_env()
    _run_health_check(expected_initialized=True)
    _run_frontend_runtime_probe()
    _maybe_login()
    pass_message("smoke_post_update completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

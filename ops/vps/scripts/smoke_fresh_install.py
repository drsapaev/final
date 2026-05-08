#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from clinic_lifecycle_common import (
    app_root,
    backend_url,
    env_bool,
    fail,
    frontend_runtime_probe_script,
    http_json,
    load_clinic_env,
    pass_message,
    read_json_payload,
    require_env,
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


def _resolve_setup_payload() -> dict[str, Any]:
    payload = read_json_payload(
        os.environ.get("SETUP_PAYLOAD_FILE"),
        os.environ.get("SETUP_PAYLOAD_JSON"),
    )
    if payload is not None:
        if not isinstance(payload, dict):
            fail("SETUP payload must be a JSON object")
        return payload

    clinic_name = require_env("SETUP_CLINIC_NAME")
    branch_name = require_env("SETUP_BRANCH_NAME")
    admin_username = require_env("SETUP_ADMIN_USERNAME")
    admin_password = require_env("SETUP_ADMIN_PASSWORD")
    admin_full_name = require_env("SETUP_ADMIN_FULL_NAME")
    admin_email = require_env("SETUP_ADMIN_EMAIL")

    payload = {
        "clinic": {
            "name": clinic_name,
            "address": os.environ.get("SETUP_CLINIC_ADDRESS"),
            "phone": os.environ.get("SETUP_CLINIC_PHONE"),
            "email": os.environ.get("SETUP_CLINIC_EMAIL"),
            "timezone": os.environ.get("SETUP_CLINIC_TIMEZONE", "Asia/Tashkent"),
            "logo_url": os.environ.get("SETUP_CLINIC_LOGO_URL"),
        },
        "branch": {
            "name": branch_name,
            "code": os.environ.get("SETUP_BRANCH_CODE"),
            "address": os.environ.get("SETUP_BRANCH_ADDRESS"),
            "phone": os.environ.get("SETUP_BRANCH_PHONE"),
            "email": os.environ.get("SETUP_BRANCH_EMAIL"),
            "timezone": os.environ.get("SETUP_BRANCH_TIMEZONE", "Asia/Tashkent"),
            "capacity": int(os.environ.get("SETUP_BRANCH_CAPACITY", "50")),
        },
        "admin": {
            "username": admin_username,
            "password": admin_password,
            "full_name": admin_full_name,
            "email": admin_email,
        },
    }
    activation_key = os.environ.get("SETUP_ACTIVATION_KEY")
    if activation_key:
        payload["activation_key"] = activation_key
    return payload


def _payload_value(payload: dict[str, Any], section: str, key: str) -> str | None:
    section_value = payload.get(section)
    if not isinstance(section_value, dict):
        return None
    value = section_value.get(key)
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _post_setup_initialize(payload: dict[str, Any]) -> dict[str, Any]:
    status, response, raw = http_json(
        "POST",
        f"{backend_url()}/api/v1/setup/initialize",
        payload=payload,
    )
    if status != 200 or not isinstance(response, dict):
        fail(f"setup initialize failed: HTTP {status} {_safe_payload(response or raw)}")
    if not response.get("initialized"):
        fail(f"setup initialize returned unexpected payload: {_safe_payload(response)}")
    return response


def _maybe_login(payload: dict[str, Any]) -> None:
    require_login = env_bool(
        "SMOKE_REQUIRE_LOGIN",
        default=True,
    )
    if not require_login:
        return

    username = os.environ.get("SMOKE_LOGIN_USERNAME") or _payload_value(payload, "admin", "username")
    password = os.environ.get("SMOKE_LOGIN_PASSWORD") or _payload_value(payload, "admin", "password")
    if not username or not password:
        fail(
            "Login smoke requested but username/password are missing. "
            "Provide SMOKE_LOGIN_USERNAME/SMOKE_LOGIN_PASSWORD or SETUP_ADMIN_*."
        )

    status, response, raw = http_json(
        "POST",
        f"{backend_url()}/api/v1/auth/minimal-login",
        payload={"username": username, "password": password, "remember_me": False},
    )
    if status != 200 or not isinstance(response, dict):
        fail(f"Login smoke failed: HTTP {status} {_safe_payload(response or raw)}")
    if not response.get("access_token"):
        fail(f"Login smoke returned no access token: {_safe_payload(response)}")


def main() -> int:
    load_clinic_env()
    payload = _resolve_setup_payload()

    status_status, status_payload, status_raw = http_json(
        "GET",
        f"{backend_url()}/api/v1/setup/status",
    )
    if status_status != 200 or not isinstance(status_payload, dict):
        fail(
            "setup/status check before install failed: "
            f"HTTP {status_status} {_safe_payload(status_payload or status_raw)}"
        )
    if bool(status_payload.get("initialized")):
        fail("Fresh install smoke expected an uninitialized deployment before setup")

    _run_health_check(expected_initialized=False)
    _run_frontend_runtime_probe()
    initialize_response = _post_setup_initialize(payload)
    _run_health_check(expected_initialized=True)
    _maybe_login(payload)

    print(f"SETUP_BRANCH_ID={initialize_response.get('branch_id')}", flush=True)
    print(f"SETUP_ADMIN_USER_ID={initialize_response.get('admin_user_id')}", flush=True)
    print(
        f"SETUP_ACTIVATION_APPLIED={bool(initialize_response.get('activation_applied'))}",
        flush=True,
    )
    pass_message("smoke_fresh_install completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

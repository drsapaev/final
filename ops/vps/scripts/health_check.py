#!/usr/bin/env python3
from __future__ import annotations

import json
import os
from pathlib import Path

from clinic_lifecycle_common import (
    backend_url,
    fail,
    http_json,
    load_clinic_env,
    pass_message,
    public_url,
)


def _expect_setup_status(expected: bool | None) -> None:
    if expected is None:
        return
    status, payload, raw = http_json("GET", f"{backend_url()}/api/v1/setup/status")
    if status != 200 or not isinstance(payload, dict):
        fail(f"setup/status check failed: HTTP {status} {raw}")
    actual = bool(payload.get("initialized"))
    if actual is not expected:
        fail(f"setup/status mismatch: expected initialized={expected}, got {actual}")


def main() -> int:
    load_clinic_env()

    expected_setup = os.environ.get("EXPECTED_SETUP_INITIALIZED")
    expected_bool = None
    if expected_setup is not None:
        expected_bool = expected_setup.strip().lower() in {"1", "true", "yes", "on"}

    status, payload, raw = http_json("GET", f"{backend_url()}/api/v1/health")
    if status != 200 or not isinstance(payload, dict):
        fail(f"backend health failed: HTTP {status} {raw}")

    health_ok = payload.get("status") in {"ok", "healthy", True} or payload.get("ok") is True
    if not health_ok:
        fail(f"backend health payload unexpected: {payload}")

    status, docs_payload, docs_raw = http_json("GET", f"{backend_url()}/docs")
    if status != 200:
        fail(f"backend docs unavailable: HTTP {status} {docs_raw}")

    public = public_url()
    status, _, public_raw = http_json(
        "GET",
        public,
        headers={"Accept": "text/html,*/*;q=0.8"},
    )
    if status != 200:
        fail(f"public frontend unavailable at {public}: HTTP {status} {public_raw}")

    _expect_setup_status(expected_bool)

    pass_message("health_check completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

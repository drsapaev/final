"""
Deterministic RBAC routing check entrypoint.

Wave 1.5 intent:
- eliminate flaky environment-coupled role checks (401/429 from live login/rate limits);
- keep one reproducible signal based on integration RBAC matrix tests.

Usage:
- default (CI-safe): `python test_role_routing.py`
- optional advisory live smoke: `python test_role_routing.py --live-smoke`
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

import requests


REPO_BACKEND_ROOT = Path(__file__).resolve().parent
DEFAULT_BASE_URL = "http://127.0.0.1:8000"


def run_rbac_matrix_pytest() -> int:
    """Run deterministic RBAC matrix tests and return pytest exit code."""
    cmd = [sys.executable, "-m", "pytest", "tests/integration/test_rbac_matrix.py", "-q"]
    print("Running deterministic RBAC matrix check:")
    print(" ", " ".join(cmd))
    result = subprocess.run(cmd, cwd=REPO_BACKEND_ROOT, check=False)
    return result.returncode


def run_live_smoke(base_url: str) -> int:
    """
    Optional advisory check against a running backend instance.

    This does not replace deterministic matrix tests and is intentionally narrow:
    it only checks health endpoint reachability.
    """
    print("\nRunning advisory live smoke check:")
    print(" ", f"GET {base_url}/api/v1/health")
    try:
        response = requests.get(f"{base_url}/api/v1/health", timeout=5)
    except requests.RequestException as exc:
        print(f"LIVE-SMOKE WARN: health check request failed: {exc}")
        return 1

    if response.status_code != 200:
        print(f"LIVE-SMOKE WARN: unexpected health status {response.status_code}")
        return 1

    print("LIVE-SMOKE OK: backend health endpoint is reachable")
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic role-routing/RBAC check wrapper")
    parser.add_argument(
        "--live-smoke",
        action="store_true",
        help="Run additional non-deterministic advisory live smoke check.",
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help=f"Backend URL for --live-smoke (default: {DEFAULT_BASE_URL})",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix_code = run_rbac_matrix_pytest()
    if matrix_code != 0:
        print("\nFAIL: deterministic RBAC matrix check failed.")
        return matrix_code

    print("\nPASS: deterministic RBAC matrix check passed.")

    if args.live_smoke:
        smoke_code = run_live_smoke(args.base_url)
        if smoke_code != 0:
            print("ADVISORY: live smoke check failed (non-deterministic environment issue).")
            return smoke_code
        print("PASS: advisory live smoke check passed.")
    else:
        print("INFO: live smoke check skipped (use --live-smoke to enable).")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

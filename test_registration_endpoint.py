#!/usr/bin/env python3
"""Retired root manual registration endpoint probe."""

from __future__ import annotations

import sys

MESSAGE = """
test_registration_endpoint.py is retired.

This root-level manual probe used a copied JWT and live localhost registrar API
assumptions outside the canonical test suites. Use backend/tests or explicit
env-driven registrar smoke scripts instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

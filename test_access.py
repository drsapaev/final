#!/usr/bin/env python3
"""Retired root manual access probe."""

from __future__ import annotations

import sys

MESSAGE = """
test_access.py is retired.

This root-level manual probe used built-in credentials and live localhost API
assumptions outside the canonical test suites. Use backend/tests, frontend/e2e,
or an env-driven smoke check instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

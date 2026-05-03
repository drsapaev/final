#!/usr/bin/env python3
"""Retired root manual services grouping probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_services_grouping.py is retired.

This root-level manual probe used built-in credentials or live localhost API
assumptions outside the canonical test suites. Use frontend/e2e with env-driven
credentials or backend/tests instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

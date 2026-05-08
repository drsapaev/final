#!/usr/bin/env python3
"""Retired root manual user dump probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_users.py is retired.

This root-level manual helper queried and printed user account state outside
the canonical test suites. Use backend/tests or explicit Postgres diagnostics
instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

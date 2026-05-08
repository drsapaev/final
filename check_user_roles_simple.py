#!/usr/bin/env python3
"""Retired root manual SQLite user roles probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_user_roles_simple.py is retired.

This root-level manual probe opened the legacy SQLite database file directly to inspect role state.
Use backend/tests or explicit Postgres diagnostics instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired root manual SQLite current database probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_db_current.py is retired.

This root-level manual probe opened the legacy SQLite database file directly with fixed historical
dates. PostgreSQL plus Alembic is the runtime schema source of truth; use
backend/tests or explicit Postgres diagnostics instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

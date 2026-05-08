#!/usr/bin/env python3
"""Retired root manual SQLite recent visits probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_recent_visits.py is retired.

This root-level manual probe opened the legacy SQLite database file directly. PostgreSQL plus Alembic
is the runtime schema source of truth; use backend/tests or explicit Postgres
diagnostics instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

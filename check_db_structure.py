#!/usr/bin/env python3
"""Retired root manual SQLite database structure probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_db_structure.py is retired.

This root-level manual probe inspected SQLite schema state outside Alembic.
Use Alembic migrations, backend/tests, or explicit Postgres diagnostics instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

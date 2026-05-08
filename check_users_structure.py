#!/usr/bin/env python3
"""Retired root manual SQLite users structure probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_users_structure.py is retired.

This root-level manual probe opened the legacy SQLite database file directly
and printed user schema/state. Use Alembic migrations, backend/tests, or
explicit Postgres diagnostics instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

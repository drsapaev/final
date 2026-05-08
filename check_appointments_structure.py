#!/usr/bin/env python3
"""Retired root manual SQLite appointments structure probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_appointments_structure.py is retired.

This root-level manual probe opened the legacy SQLite database file directly. PostgreSQL plus
Alembic is the runtime schema source of truth; use backend/tests or migration
inspection tools instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired legacy planned-date schema mutator."""

from __future__ import annotations

import sys

MESSAGE = """
add_planned_date.py is retired.

Schema changes are owned by Alembic migrations against the current PostgreSQL
runtime. Do not mutate a local database file from this script.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
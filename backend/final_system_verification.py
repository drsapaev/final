#!/usr/bin/env python3
"""Retired manual final-system verification script."""

from __future__ import annotations

import sys

MESSAGE = """
final_system_verification.py is retired.

This stale manual verification used built-in role credentials and legacy local
database checks. Use env-driven smoke checks against the current
Postgres/Alembic runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

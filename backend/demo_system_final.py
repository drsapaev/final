#!/usr/bin/env python3
"""Retired manual demo smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
demo_system_final.py is retired.

This stale manual demo used built-in role credentials. Use env-driven smoke
checks against the current Postgres/Alembic runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

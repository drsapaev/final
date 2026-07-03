#!/usr/bin/env python3
"""Retired legacy root quick-check wrapper."""

from __future__ import annotations

import sys


MESSAGE = """
quick_check.py is retired.

This legacy wrapper depended on a local clinic.db file and shell-invoked stale
smoke scripts. Use targeted pytest checks or the current CI/runbook commands
against the PostgreSQL/Alembic runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

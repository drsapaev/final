#!/usr/bin/env python3
"""Retired root manual auth/role repair helper."""

from __future__ import annotations

import sys

MESSAGE = """
fix_auth_issues.py is retired.

This root-level helper imported runtime database models at module load, mutated
admin role assignments directly, and minted a short-lived JWT for localhost
API probes. Auth and admin repair must use the guarded backend helpers and the
current PostgreSQL/Alembic runtime contract instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

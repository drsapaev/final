#!/usr/bin/env python3
"""Retired async admin bootstrap helper."""

from __future__ import annotations

import sys

MESSAGE = """
scripts/ensure_admin_async.py is retired.

This legacy helper created the bootstrap admin with a built-in credential.
Admin bootstrap belongs to the canonical Postgres/Alembic path:

  python -m app.scripts.ensure_admin

Set ADMIN_PASSWORD before creating the bootstrap admin.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

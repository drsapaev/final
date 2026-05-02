#!/usr/bin/env python3
"""Retired legacy admin auth repair helper."""

from __future__ import annotations

import sys

MESSAGE = """
fix_admin_auth.py is retired.

This legacy helper directly modified admin credentials in a local SQLite
database. Admin bootstrap and controlled credential reset belong to the
canonical Postgres/Alembic path:

  python -m app.scripts.ensure_admin

Set ADMIN_PASSWORD and, for controlled reset on an initialized instance, set
ADMIN_RESET_PASSWORD=1 and ENSURE_ADMIN_ALLOW_INITIALIZED=1.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

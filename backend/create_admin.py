#!/usr/bin/env python3
"""Retired legacy admin bootstrap helper."""

from __future__ import annotations

import sys

MESSAGE = """
create_admin.py is retired.

This legacy helper created an admin user by writing directly to a local
database with stale password columns. Admin bootstrap belongs to the canonical
Postgres/Alembic path:

  python -m app.scripts.ensure_admin

Set ADMIN_PASSWORD before creating the bootstrap admin. For controlled password
reset on an initialized instance, also set ADMIN_RESET_PASSWORD=1 and
ENSURE_ADMIN_ALLOW_INITIALIZED=1.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

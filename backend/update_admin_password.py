#!/usr/bin/env python3
"""Retired legacy admin password update helper."""

from __future__ import annotations

import sys

MESSAGE = """
update_admin_password.py is retired.

This legacy helper updated the bootstrap admin credential through a local
database path. Controlled admin password reset belongs to the canonical
Postgres/Alembic path:

  python -m app.scripts.ensure_admin

Set ADMIN_PASSWORD, ADMIN_RESET_PASSWORD=1, and
ENSURE_ADMIN_ALLOW_INITIALIZED=1 for controlled recovery.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

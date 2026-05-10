#!/usr/bin/env python3
"""Retired legacy database patch helper.

This script used to mutate the users table directly and seed role users with
tracked password hashes. Database schema is owned by Alembic, and role-user
passwords must come from environment variables through the supported role
maintenance script.
"""

from __future__ import annotations


MESSAGE = """
add_missing_columns.py is retired and intentionally does not modify the database.

Use the canonical database and role-user paths instead:

  1. Apply schema changes through Alembic migrations.
  2. Manage role users with backend/app/scripts/ensure_roles.py.

Example role-user command from the backend runtime environment:

  CONFIRM_ENSURE_ROLES=1 ENSURE_ROLES_REGISTRAR_PASSWORD=<set-locally> python -m app.scripts.ensure_roles

No tracked demo passwords or static password hashes are safe to use here.
""".strip()


def main() -> int:
    print(MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

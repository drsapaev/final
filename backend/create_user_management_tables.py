#!/usr/bin/env python3
"""Retired legacy user management schema helper.

User management schema is owned by Alembic migrations. RBAC data must use the
current role/permission models and seed workflow, not ad-hoc schema helpers.
"""

from __future__ import annotations

import sys


MESSAGE = """
create_user_management_tables.py is retired.

This legacy helper bypassed Alembic and used stale RBAC table contracts. Apply
database schema changes through Alembic migrations and seed RBAC data through
the current model-owned workflow.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

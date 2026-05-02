"""Retired destructive departments reset helper.

The departments schema is owned by Alembic migrations. Department seed data can
be applied with `python init_departments.py` after `alembic upgrade head`.
"""
from __future__ import annotations

import sys


MESSAGE = """
reset_departments_table.py is retired.

This legacy helper used to drop and recreate the departments table directly.
Use Alembic migrations for schema changes and run `python init_departments.py`
only when seed data is needed.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

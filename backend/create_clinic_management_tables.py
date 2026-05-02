"""Retired legacy clinic management schema helper.

Clinic management tables are owned by Alembic migrations. Run
`alembic upgrade head` instead of creating tables from SQLAlchemy metadata.
"""
from __future__ import annotations

import sys


MESSAGE = """
create_clinic_management_tables.py is retired.

Clinic management schema is managed by Alembic. This helper intentionally does
not connect to the database, create schema from SQLAlchemy metadata, or inspect
SQLite internals.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

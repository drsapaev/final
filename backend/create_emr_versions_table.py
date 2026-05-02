"""Retired legacy EMR versions schema helper.

The `emr_versions` table is owned by Alembic migrations. Run
`alembic upgrade head` instead of creating tables from SQLAlchemy metadata.
"""
from __future__ import annotations

import sys


MESSAGE = """
create_emr_versions_table.py is retired.

The emr_versions schema is managed by Alembic. This helper intentionally does
not connect to the database or create schema from SQLAlchemy metadata.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

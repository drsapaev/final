#!/usr/bin/env python3
"""Retired legacy departments table reset helper.

Department schema is owned by Alembic migrations. This root helper no longer
drops or recreates local SQLite tables, because that can destroy data, hide
schema drift, and bypass the PostgreSQL + Alembic source of truth.
"""

from __future__ import annotations


MESSAGE = """
backend/reset_departments_table.py is retired.

Do not reset departments through direct SQLite table drops or metadata table
creation. Apply schema changes through Alembic migrations instead:

  cd backend
  alembic upgrade head

Use supported seed or admin flows for department data corrections.
""".strip()


def main() -> int:
    print(MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

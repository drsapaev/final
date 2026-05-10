#!/usr/bin/env python3
"""Retired legacy EMR versions table helper.

Schema creation is owned by Alembic migrations. This root helper no longer
performs direct SQLAlchemy metadata table creation, because that can hide schema
drift and bypass the PostgreSQL + Alembic source of truth.
"""

from __future__ import annotations


MESSAGE = """
backend/create_emr_versions_table.py is retired.

Do not create EMR version tables through direct metadata table creation.
Apply schema changes through Alembic migrations instead:

  cd backend
  alembic upgrade head
""".strip()


def main() -> int:
    print(MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

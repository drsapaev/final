#!/usr/bin/env python3
"""Retired legacy medical records schema helper.

Database schema is owned by Alembic migrations. Clinical data must never be
created by an ad-hoc local database helper.
"""

from __future__ import annotations

import sys


MESSAGE = """
create_medical_records_table.py is retired.

This legacy helper created schema outside Alembic and inserted sample clinical
data. Use an Alembic migration for schema changes and approved seed/fixture
paths for non-production test data.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

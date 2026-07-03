#!/usr/bin/env python3
"""Retired legacy registrar schema patch helper.

Registrar appointment and patient fields are owned by SQLAlchemy models and
Alembic migrations. This helper used to mutate database schema directly and is
kept only as a fail-fast pointer to the canonical migration flow.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/add_registrar_fields.py is retired.

Do not add registrar columns with an ad-hoc schema patch helper. PostgreSQL +
Alembic are the database source of truth. Apply the canonical migrations instead:

  cd backend
  alembic upgrade head
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

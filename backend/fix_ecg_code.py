#!/usr/bin/env python3
"""Retired legacy ECG service-code helper.

Service catalog changes are owned by migrations, seed data, or supported admin
flows. This root helper no longer mutates a local SQLite database directly.
"""

from __future__ import annotations


MESSAGE = """
backend/fix_ecg_code.py is retired.

Do not update ECG service codes through a direct SQLite UPDATE. Apply catalog
changes through the canonical migration, seed, or admin-service path instead.

For schema changes:

  cd backend
  alembic upgrade head
""".strip()


def main() -> int:
    print(MESSAGE)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired legacy schema repair helper.

Database schema changes are managed by Alembic migrations. This file is kept as
a fail-closed stub so old runbooks or shell history cannot silently mutate the
runtime database or create users with embedded password hashes.
"""

import sys


MESSAGE = """
add_missing_columns.py is retired.

Use Alembic migrations for schema changes and the hardened bootstrap helpers for
user creation. This legacy helper intentionally does not connect to the
database, change schema, or seed users.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

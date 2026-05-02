#!/usr/bin/env python3
"""Retired legacy webhook schema helper.

Webhook schema is owned by Alembic migrations and the current runtime models.
"""

from __future__ import annotations

import sys


MESSAGE = """
create_webhook_tables.py is retired.

This legacy helper hand-wrote webhook schema outside Alembic. Use Alembic
migrations for schema changes and the current webhook models as the source of
truth.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

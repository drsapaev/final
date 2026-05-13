#!/usr/bin/env python3
"""Retired legacy services schema helper."""

from __future__ import annotations

import sys


MESSAGE = """
create_services_tables_manually.py is retired.

This legacy helper created services schema in a local database outside Alembic.
Use Alembic migrations for service schema changes and seed_services.py for the
approved service catalog seed workflow.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired legacy file-system schema helper."""

from __future__ import annotations

import sys


MESSAGE = """
create_file_system_tables.py is retired.

This legacy helper wrote a local database directly, created file-system schema
outside Alembic, and seeded storage/folder/quota data. Use Alembic migrations
for schema changes and the approved file-system settings or seed workflow for
runtime data.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

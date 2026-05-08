#!/usr/bin/env python3
"""Retired legacy Telegram schema/config helper.

Telegram tables are owned by Alembic migrations and runtime configuration must
come from the approved settings/admin workflow.
"""

from __future__ import annotations

import sys


MESSAGE = """
create_telegram_tables.py is retired.

This legacy helper wrote a local database directly, created Telegram schema
outside Alembic, and seeded a placeholder bot configuration. Use Alembic for
schema changes and the approved Telegram settings workflow for configuration.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

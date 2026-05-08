"""Retired legacy SQLite telegram-template schema patch.

Telegram template setup belongs to the canonical application/database path.
Use backend/setup_telegram_templates.py with its explicit confirmation guard for
local setup, or Alembic-managed PostgreSQL migrations for runtime schema.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/create_telegram_templates.py is retired. "
        "Use backend/setup_telegram_templates.py for confirmed local setup."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

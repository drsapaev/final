#!/usr/bin/env python3
"""Retired legacy server-startup smoke helper.

This root script used to force a local SQLite DATABASE_URL and permissive
development flags before importing the application. That bypassed the
PostgreSQL + Alembic runtime contract and could hide startup drift.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/test_server_startup.py is retired.

Do not validate backend startup by forcing a local SQLite database URL or
permissive CORS/WebSocket development flags. Use the canonical test suite or
start the backend with a configured PostgreSQL DATABASE_URL instead:

  cd backend
  python -m pytest tests/unit
  python -m uvicorn app.main:app --host 127.0.0.1 --port 18000
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

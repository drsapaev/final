#!/usr/bin/env python3
"""Retired legacy queue-entry diagnostic helper.

This root script used to inspect queue rows through a local file-backed
database. Queue behavior must be checked through canonical API/integration
coverage against the configured PostgreSQL/Alembic runtime.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/update_queue_entries.py is retired.

Do not inspect or repair queue entries through a local database file. Use
canonical queue tests and runtime API checks against the configured backend
instead:

  cd backend
  python -m pytest tests/integration/test_online_queue.py
  python -m pytest tests/unit/test_service_repository_boundary.py
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

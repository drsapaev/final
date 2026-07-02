#!/usr/bin/env python3
"""Retired legacy CI simulation helper.

This script used to install dependencies, create ad-hoc database tables, start
a local server, and run stale smoke helpers outside the canonical CI pipeline.
That path bypassed the PostgreSQL + Alembic runtime contract and duplicated
GitHub Actions checks.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/test_ci_simulation.py is retired.

Do not simulate CI by creating ad-hoc local database tables or launching stale
root smoke scripts. Use the maintained GitHub Actions workflow, or run focused
checks directly against the configured PostgreSQL/Alembic environment:

  cd backend
  python -m pytest tests
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

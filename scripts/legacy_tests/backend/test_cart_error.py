#!/usr/bin/env python3
"""Retired legacy cart diagnostic helper.

This root script used to open a local file-backed database directly while
debugging registrar cart failures. Cart behavior is now validated through the
canonical FastAPI test suite and the configured PostgreSQL/Alembic runtime.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/test_cart_error.py is retired.

Do not diagnose registrar cart behavior by opening a local file-backed
database. Use the canonical API/integration tests against the configured
runtime instead:

  cd backend
  python -m pytest tests/integration/test_admin_finance_transactions.py
  python -m pytest tests/unit/test_service_repository_boundary.py
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

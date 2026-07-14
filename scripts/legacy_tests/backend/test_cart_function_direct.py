#!/usr/bin/env python3
"""Retired legacy direct cart-function diagnostic helper.

This root script used to import a registrar endpoint function directly and bind
it to a local file-backed database session. That bypassed the API contract,
dependency injection, RBAC, and the PostgreSQL/Alembic runtime source of truth.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/test_cart_function_direct.py is retired.

Do not call registrar cart endpoint functions directly against a local
file-backed database. Use canonical API/integration coverage against the
configured runtime instead:

  cd backend
  python -m pytest tests/integration/test_admin_finance_transactions.py
  python -m pytest tests/integration/test_e2e_clinic.py
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

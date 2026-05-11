#!/usr/bin/env python3
"""Retired legacy payment-webhook smoke helper.

This root script used to force a local file-backed test database, create
ad-hoc tables with SQLAlchemy metadata, and probe stale webhook routes. That
bypassed the PostgreSQL + Alembic runtime contract and could hide payment route
drift.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/test_payment_webhooks.py is retired.

Do not validate payment webhooks by forcing a local file-backed database or
creating schema from SQLAlchemy metadata. Use canonical payment webhook tests
against the configured PostgreSQL/Alembic environment instead:

  cd backend
  python -m pytest tests/integration/test_notification_catalog_slice2_online_payments.py
  python -m pytest tests/unit/test_service_repository_boundary.py
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

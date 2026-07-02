#!/usr/bin/env python3
"""Retired legacy procedure-distribution diagnostic helper.

This root script used to inspect service distribution through a local
file-backed database. Service catalog behavior must be checked through
canonical tests and the configured PostgreSQL/Alembic runtime.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/test_procedures_distribution.py is retired.

Do not validate procedure/service distribution by reading a local database file.
Use canonical backend tests and runtime API checks against the configured
environment instead:

  cd backend
  python -m pytest tests/unit/test_no_legacy_ports_in_active_text.py
  python -m pytest tests/unit/test_service_repository_boundary.py
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

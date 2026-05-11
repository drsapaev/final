#!/usr/bin/env python3
"""Retired legacy direct-auth diagnostic helper.

This script previously inspected user credential records directly from a local
database file. Authentication checks must go through canonical tests and
runtime auth contracts instead of local database introspection.
"""

from __future__ import annotations

import sys


MESSAGE = """
backend/test_auth_direct.py is retired.

Do not inspect stored credential records through local database files. Use the
canonical auth tests and current login smoke helpers against the configured
PostgreSQL runtime instead:

  cd backend
  python -m pytest tests/integration/test_rbac_matrix.py
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Retired manual CRUD smoke.

This root script used to open the configured runtime database through get_db()
and inspect webhook/payment tables. Use isolated backend/tests instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_crud_functions.py is retired. "
        "Use backend/tests with an isolated test database instead."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

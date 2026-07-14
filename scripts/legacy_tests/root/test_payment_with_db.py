#!/usr/bin/env python3
"""Retired root manual payment smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_payment_with_db.py is retired.

This root-level helper looked like a pytest module, called live payment
endpoints, and mutated a local legacy SQLite database file. Use backend/tests payment
coverage or an explicit, env-driven payment smoke check against the current
Postgres/Alembic runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired root manual auth smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_auth_direct.py is retired.

This root-level manual script used built-in credentials or local database
assumptions and is outside the backend pytest suite. Use backend/tests pytest
fixtures or an env-driven smoke check against the current Postgres/Alembic
runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

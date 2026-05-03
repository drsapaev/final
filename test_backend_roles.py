#!/usr/bin/env python3
"""Retired root manual backend role probe."""

from __future__ import annotations

import sys

MESSAGE = """
test_backend_roles.py is retired.

This root-level manual probe mixed built-in credentials, live localhost API
calls, and direct SQLite access outside the canonical Postgres + Alembic
runtime contract. Use backend/tests, frontend/e2e, or an env-driven smoke check
instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

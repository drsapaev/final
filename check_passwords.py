#!/usr/bin/env python3
"""Retired root manual password probing helper."""

from __future__ import annotations

import sys

MESSAGE = """
check_passwords.py is retired.

This root-level helper tested guessed credentials against local user hashes and
printed password-hash fragments. Use backend/tests pytest fixtures or an
explicit, env-driven smoke check against the current Postgres/Alembic runtime
instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

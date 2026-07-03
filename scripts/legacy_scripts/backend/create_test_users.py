#!/usr/bin/env python3
"""Retired root manual test-user creation helper.

This legacy helper forced a local SQLite database and used built-in demo role
passwords. Use Alembic-backed setup plus canonical backend/tests fixtures or
env-driven smoke helpers instead.
"""

from __future__ import annotations

import sys

MESSAGE = (
    "Retired root manual test-user creation helper. "
    "Use Alembic-backed setup plus canonical backend/tests fixtures or "
    "env-driven smoke helpers instead."
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired manual doctor/nurse auth repair helper."""

from __future__ import annotations

import sys

MESSAGE = """
fix_doctor_nurse_auth.py is retired.

This manual helper used built-in role credentials and local database mutation.
Use the canonical PostgreSQL/Alembic runtime and admin reset/bootstrap flow
instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

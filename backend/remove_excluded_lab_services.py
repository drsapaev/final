#!/usr/bin/env python3
"""Retired legacy destructive lab service helper."""

from __future__ import annotations

import sys


MESSAGE = """
remove_excluded_lab_services.py is retired.

This legacy helper deleted lab services from a local database directly. Lab
catalog membership belongs in seed_services.py and the canonical lab seed data
and Alembic migrations.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired legacy lab service update helper."""

from __future__ import annotations

import sys


MESSAGE = """
update_lab_services.py is retired.

This legacy helper edited a local database directly. Lab service catalog data
belongs in seed_services.py, and lab template bindings belong in the canonical
lab seed data and Alembic migrations.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

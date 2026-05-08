#!/usr/bin/env python3
"""Retired legacy HCV lab service data patch helper."""

from __future__ import annotations

import sys


MESSAGE = """
add_missing_hcv_service.py is retired.

This legacy helper edited a local database directly. The HCV lab service entry
belongs in seed_services.py, and lab template bindings belong in the canonical
lab seed data and Alembic migrations.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

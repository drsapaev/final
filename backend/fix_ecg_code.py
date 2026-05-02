#!/usr/bin/env python3
"""Retired legacy ECG service-code repair helper."""

from __future__ import annotations

import sys


MESSAGE = """
fix_ecg_code.py is retired.

This legacy helper edited a local database file directly and changed service
codes outside the approved schema and seed workflows. Use Alembic migrations or
the canonical service seed/update workflow for service data changes.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

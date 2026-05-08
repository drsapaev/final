#!/usr/bin/env python3
"""Retired root manual ECG queue inspection script."""

from __future__ import annotations

import sys

MESSAGE = """
test_ecg_queue.py is retired.

This root-level helper looked like a pytest module but inspected one local
visit id through a stale database import path. Use backend/tests pytest
fixtures or an explicit, env-driven queue smoke check against the current
Postgres/Alembic runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

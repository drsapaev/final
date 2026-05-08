#!/usr/bin/env python3
"""Retired root manual queue API smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_queue_api.py is retired.

This root-level helper looked like a pytest module but called live queue
endpoints with fake tokens and local backend assumptions. Use backend/tests
pytest coverage or an explicit, env-driven smoke check against the current
runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

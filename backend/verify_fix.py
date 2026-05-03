#!/usr/bin/env python3
"""Retired manual fix verification smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
verify_fix.py is retired.

This manual script used built-in credentials against a live backend. Use
backend/tests pytest coverage or an env-driven smoke check instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

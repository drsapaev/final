#!/usr/bin/env python3
"""Retired manual integration smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
integration_test.py is retired.

This manual script used built-in credentials or direct runtime assumptions
outside the backend pytest suite. Use backend/tests pytest coverage or an
env-driven smoke check instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

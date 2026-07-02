#!/usr/bin/env python3
"""Retired root manual database creation smoke script.

This root-level script used built-in demo credentials and is intentionally kept
outside the canonical pytest suite. Use Alembic and canonical backend/tests
fixtures instead.
"""

from __future__ import annotations

import sys

MESSAGE = (
    "Retired root manual database creation smoke script. "
    "Use Alembic and canonical backend/tests fixtures instead."
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

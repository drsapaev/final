#!/usr/bin/env python3
"""Retired root manual fixed upload smoke script.

This root-level script used built-in demo credentials and is intentionally kept
outside the canonical pytest suite. Use backend/tests fixtures or env-driven
smoke checks instead.
"""

from __future__ import annotations

import sys

MESSAGE = (
    "Retired root manual fixed upload smoke script. "
    "Use backend/tests fixtures or env-driven smoke checks instead."
)


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

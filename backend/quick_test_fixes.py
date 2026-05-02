#!/usr/bin/env python3
"""Retired manual quick-fixes smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
quick_test_fixes.py is retired.

This stale manual smoke script used built-in credentials. Use env-driven smoke
checks against the current backend runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

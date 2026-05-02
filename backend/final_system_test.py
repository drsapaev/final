#!/usr/bin/env python3
"""Retired manual final-system smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
final_system_test.py is retired.

This stale manual smoke script used built-in role credentials. Use env-driven
smoke checks against the current backend runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

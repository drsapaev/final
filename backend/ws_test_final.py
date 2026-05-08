#!/usr/bin/env python3
"""Retired final WebSocket broadcast smoke script."""

from __future__ import annotations

import sys


MESSAGE = """
ws_test_final.py is retired.

This stale manual smoke script used hardcoded admin credentials and could call
live queue/broadcast mutation endpoints. Use backend pytest coverage or an
env-driven WebSocket smoke check with explicit credentials instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

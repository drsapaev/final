#!/usr/bin/env python3
"""Retired root WebSocket smoke script."""

from __future__ import annotations

import sys


MESSAGE = """
ws_test.py is retired.

This stale manual smoke script used hardcoded local WebSocket URLs. Use backend
pytest coverage or an env-driven WebSocket smoke check against the current
runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

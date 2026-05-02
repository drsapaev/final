#!/usr/bin/env python3
"""Retired root manual simple endpoints smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_simple_endpoints.py is retired.

This root-level manual script used direct runtime access outside the backend
pytest suite. Use backend/tests pytest fixtures against current service or API
contracts instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

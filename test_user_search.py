#!/usr/bin/env python3
"""Retired root manual user-search smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_user_search.py is retired.

This root-level helper looked like a pytest module but inspected a specific
local MCP test user. Use backend/tests pytest fixtures or an explicit,
env-driven smoke check against the current runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

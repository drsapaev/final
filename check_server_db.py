#!/usr/bin/env python3
"""Retired root manual server database inspection helper."""

from __future__ import annotations

import sys

MESSAGE = """
check_server_db.py is retired.

This root-level helper inspected a specific local MCP test user and printed
password-hash fragments. Use backend/tests pytest fixtures or an explicit,
env-driven smoke check against the current runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired root manual authenticated MCP API smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_mcp_api_auth.py is retired.

This root-level helper looked like a pytest module but used built-in local
credentials against live MCP endpoints. Use backend/tests pytest fixtures or an
explicit, env-driven smoke check against the current runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

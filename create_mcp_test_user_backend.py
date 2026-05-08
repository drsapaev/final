#!/usr/bin/env python3
"""Retired backend MCP test-user bootstrap helper."""

from __future__ import annotations

import sys

MESSAGE = """
create_mcp_test_user_backend.py is retired.

This root-level helper created or reset a privileged MCP test user with a
built-in password. Use the canonical admin/bootstrap flow with explicit
environment-provided credentials, or create a least-privileged local test user
through the current application setup path.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

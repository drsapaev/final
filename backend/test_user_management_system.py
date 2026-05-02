#!/usr/bin/env python3
"""Retired root manual user management smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_user_management_system.py is retired.

This root-level manual script used built-in credentials and direct database
access outside the backend pytest suite. Use backend/tests pytest fixtures
against the current service contracts instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired root manual user role repair probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_user_roles.py is retired.

This root-level manual helper inspected and mutated user-role rows directly.
Use migrations, admin APIs, or focused backend tests with explicit fixtures
instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

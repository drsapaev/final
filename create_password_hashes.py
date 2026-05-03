#!/usr/bin/env python3
"""Retired manual password hash reset helper."""

from __future__ import annotations

import sys

MESSAGE = """
create_password_hashes.py is retired.

This manual helper used built-in role credentials and direct database updates.
Use the canonical admin bootstrap/reset flow with explicit environment
variables instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

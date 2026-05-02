#!/usr/bin/env python3
"""Retired flexible admin bootstrap helper."""

from __future__ import annotations

import sys

MESSAGE = """
ensure_admin_flexible.py is retired.

This legacy helper used dynamic model/session discovery and non-canonical
credential hashing fallbacks. Admin bootstrap and controlled reset belong to:

  python -m app.scripts.ensure_admin

Set ADMIN_PASSWORD before bootstrap. For controlled reset on an initialized
instance, also set ADMIN_RESET_PASSWORD=1 and ENSURE_ADMIN_ALLOW_INITIALIZED=1.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired manual notifications endpoint smoke/fix script."""

from __future__ import annotations

import sys

MESSAGE = """
fix_notifications_500.py is retired.

This stale manual script used built-in credentials and printed replacement
endpoint code instead of exercising canonical tests. Use targeted tests or an
env-driven smoke check for notification endpoints.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

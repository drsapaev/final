#!/usr/bin/env python3
"""Retired root manual API key inspection helper."""

from __future__ import annotations

import sys

MESSAGE = """
check_api_keys.py is retired.

This root-level helper read backend/.env and printed AI API key prefixes. Use
an explicit, opt-in environment smoke check that reports only presence/absence
and never prints secret material.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

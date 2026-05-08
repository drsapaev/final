#!/usr/bin/env python3
"""Retired root manual DeepSeek environment inspection script."""

from __future__ import annotations

import sys

MESSAGE = """
test_deepseek_load.py is retired.

This root-level helper executed at import time, loaded backend/.env, printed
AI API key prefixes, and imported the live AI manager during pytest collection.
Use an explicit, opt-in AI smoke check that never prints secret material.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

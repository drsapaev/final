#!/usr/bin/env python3
"""Retired root manual DeepSeek API smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_deepseek_api_direct.py is retired.

This root-level helper looked like a pytest module, called external DeepSeek
API endpoints, and printed API key prefixes. Use an explicit, env-driven smoke
check that is opt-in and never prints secret material.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

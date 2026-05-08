#!/usr/bin/env python3
"""Retired root manual AI provider inspection script."""

from __future__ import annotations

import sys

MESSAGE = """
test_ai_from_backend.py is retired.

This root-level helper looked like a pytest module and inspected local AI API
key configuration, including key prefixes. Use backend/tests pytest fixtures or
an explicit, env-driven smoke check that never prints secret material.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

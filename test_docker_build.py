#!/usr/bin/env python3
"""Retired root manual Docker build smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_docker_build.py is retired.

This root-level helper looked like a pytest module but invoked Docker as a live
environment dependency. Use the dedicated CI/build workflow or an explicit
operator smoke check instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

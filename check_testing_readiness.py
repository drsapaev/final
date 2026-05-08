#!/usr/bin/env python3
"""Retired root manual readiness probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_testing_readiness.py is retired.

This root-level manual probe used live localhost assumptions and stale startup
hints. Use canonical runbooks, backend health tests, or explicit env-driven
smoke scripts instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

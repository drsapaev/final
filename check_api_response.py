#!/usr/bin/env python3
"""Retired root manual registrar queue API probe."""

from __future__ import annotations

import sys

MESSAGE = """
check_api_response.py is retired.

This root-level manual probe called live localhost registrar endpoints with
date- and patient-specific assumptions. Use backend/tests or an explicit
env-driven smoke script instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

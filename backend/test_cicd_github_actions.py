#!/usr/bin/env python3
"""Retired root GitHub Actions smoke script."""

from __future__ import annotations

import sys


MESSAGE = """
test_cicd_github_actions.py is retired.

This root-level manual smoke script sent live HTTP requests, including Payme
webhook POSTs, outside the backend pytest suite. Use backend/tests pytest
coverage or workflow-owned transient smoke scripts instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

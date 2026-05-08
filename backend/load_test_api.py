#!/usr/bin/env python3
"""Retired duplicate load-test smoke script."""

from __future__ import annotations

import sys


MESSAGE = """
load_test_api.py is retired.

Use load_test.py with CONFIRM_LOAD_TEST=1 for manual load testing. The CI
workflow creates its own transient load_test_api.py during the workflow run.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

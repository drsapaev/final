#!/usr/bin/env python3
"""Retired root manual AI function probe."""

from __future__ import annotations

import sys

MESSAGE = """
test_problematic_functions.py is retired.

This root-level helper looked like a pytest module and probed live AI manager
behavior outside the backend pytest suite. Use backend/tests pytest fixtures or
an explicit, opt-in AI smoke check instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

"""Retired manual broadcast import diagnostic.

This root script imported queue runtime internals to inspect private broadcast
symbols. Use backend/tests for supported import and behavior checks.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_import_broadcast.py is retired. "
        "Use backend/tests for supported broadcast checks."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

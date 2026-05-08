"""Retired manual broadcast diagnostic.

This root script used to import queue runtime internals and call _broadcast
directly. Use backend/tests for isolated broadcast behavior checks.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_broadcast_direct.py is retired. "
        "Use backend/tests for isolated broadcast checks."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

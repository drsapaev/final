"""Retired manual websocket rooms diagnostic.

This root script imported the runtime ws_manager singleton to inspect room
state. Use backend/tests for isolated websocket room behavior checks.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_rooms.py is retired. "
        "Use backend/tests for isolated websocket room checks."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

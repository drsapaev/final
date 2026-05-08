"""Retired manual websocket logging diagnostic.

This root script imported app.ws.queue_ws to inspect runtime logger state.
Use backend/tests for supported websocket logging checks.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_logging_runtime.py is retired. "
        "Use backend/tests for supported websocket logging checks."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

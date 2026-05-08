"""Retired manual endpoint server.

This root script used to import the queue router and bind uvicorn on
0.0.0.0:8001. Use backend/tests or a dedicated local dev server instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_minimal_endpoint.py is retired. "
        "Use backend/tests or the canonical backend dev server instead."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

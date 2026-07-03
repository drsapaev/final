"""Retired root service diagnostic.

This script used to open a configured database session at import time. Use
backend/tests or a confirmed, env-driven smoke helper instead.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/check_services.py is retired. "
        "Use backend/tests or a confirmed service smoke helper instead."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

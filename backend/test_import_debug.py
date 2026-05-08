"""Retired manual endpoint import diagnostic.

This root script imported the appointments endpoint module to inspect private
runtime symbols. Use backend/tests for supported endpoint import checks.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_import_debug.py is retired. "
        "Use backend/tests for supported endpoint import checks."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

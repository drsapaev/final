"""Retired manual DB smoke.

Use tracked tests under backend/tests instead. This root script used to connect
to the configured runtime database at import time and print the database URL,
which is unsafe for local QA and CI-like runs.
"""

from __future__ import annotations

import sys


def main() -> int:
    print(
        "backend/test_backend_db.py is retired. "
        "Use backend/tests with an isolated test database instead."
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())

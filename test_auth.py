#!/usr/bin/env python3
"""Retired root manual auth smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_auth.py is retired.

This root-level helper looked like a pytest module but depended on backend
package import paths and called live auth/admin endpoints. Use backend/tests
pytest fixtures or an explicit, env-driven smoke check against the current
runtime instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Retired root manual backend queue smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_backend_only.py is retired.

This root-level helper looked like a pytest module but called live backend
queue endpoints with local runtime assumptions. Use backend/tests pytest
coverage or an explicit, env-driven smoke check against the current runtime
instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

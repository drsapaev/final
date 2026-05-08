#!/usr/bin/env python3
"""Retired root manual Gemini medical smoke script."""

from __future__ import annotations

import sys

MESSAGE = """
test_gemini_medical.py is retired.

This root-level helper looked like a pytest module and called external Gemini
AI functionality. Use backend/tests pytest fixtures or an explicit, opt-in
AI smoke check that never prints secret material.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

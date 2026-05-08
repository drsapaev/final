#!/usr/bin/env python3
"""Retired root visit/payment integration smoke script."""

from __future__ import annotations

import sys


MESSAGE = """
test_visit_payment_integration.py is retired.

This root-level manual smoke script sent fake Payme/Click webhook POSTs to a
live backend and could create or update visit/payment state. Use backend/tests
pytest fixtures for payment webhook and visit-payment contracts instead.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

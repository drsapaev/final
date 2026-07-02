#!/usr/bin/env python3
"""Retired legacy service-code update helper."""

from __future__ import annotations

import sys


MESSAGE = """
update_services_codes.py is retired.

This legacy helper edited a local database directly and contained stale service
code mappings. Service catalog codes belong in seed_services.py and runtime
service-code ownership belongs in app.services.service_mapping.
""".strip()


def main() -> int:
    print(MESSAGE, file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())

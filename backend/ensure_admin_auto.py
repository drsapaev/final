#!/usr/bin/env python3
"""Compatibility wrapper for the canonical admin bootstrap script.

Windows restore smoke tooling still invokes this filename. Keep the entrypoint,
but delegate all behavior to app.scripts.ensure_admin so password hashing,
initialized-instance guards, and database ownership stay in one place.
"""

from __future__ import annotations

import sys
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.scripts.ensure_admin import ensure_admin  # noqa: E402


def main() -> int:
    info = ensure_admin()
    print("[ensure_admin_auto]", info)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

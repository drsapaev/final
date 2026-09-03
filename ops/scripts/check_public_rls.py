#!/usr/bin/env python3
"""Assert every public table has Row Level Security enabled.

CI guardrail born from the 2026-09-02 Supabase incident
(`rls_disabled_in_public`): salary tables created out-of-band stayed
without RLS for days until a vendor letter arrived. This check runs
against a disposable PostgreSQL right after `alembic upgrade head`
(see the backend-tests job) and fails the build when ANY table in the
``public`` schema has ``relrowsecurity = false`` — so the next table
without RLS breaks CI before merge, not production later.

Usage:
    DATABASE_URL=postgresql+psycopg://... python ops/scripts/check_public_rls.py

Exit codes: 0 = all tables RLS-enabled, 1 = violations (or empty schema),
2 = connection/setup error.
"""
from __future__ import annotations

import os
import sys

import sqlalchemy as sa

QUERY_TABLES = sa.text(
    """
    SELECT c.relname, c.relrowsecurity
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p')
    """
)


def main() -> int:
    url = os.environ.get("DATABASE_URL", "").strip()
    if not url:
        print("check_public_rls: DATABASE_URL is not set", file=sys.stderr)
        return 2

    try:
        engine = sa.create_engine(url)
        with engine.connect() as conn:
            rows = conn.execute(QUERY_TABLES).fetchall()
    except Exception as exc:  # noqa: BLE001 - report and fail
        print(f"check_public_rls: query failed: {exc}", file=sys.stderr)
        return 2

    if not rows:
        print(
            "check_public_rls: no public tables found — schema upgrade did not run?",
            file=sys.stderr,
        )
        return 1

    off = sorted(name for name, rls in rows if not rls)
    total = len(rows)
    if off:
        print(
            f"check_public_rls: FAIL — {len(off)}/{total} public tables have RLS disabled:"
        )
        for name in off:
            print(f"  - {name}")
        print(
            "Fix: enable RLS in the table's creating migration (see "
            "0046_enable_rls / 0050_enable_rls_sweep for the pattern)."
        )
        return 1

    print(f"check_public_rls: OK — {total}/{total} public tables have RLS enabled")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auto-fix for orphan references based on audit_orphans.csv.
Strategy: SET NULL for child foreign key columns when parent row is missing.
Portable for SQLite and Postgres.
"""
import os
import sys

import sqlalchemy as sa

SQLS = []

def _is_sqlite_url(url: str) -> bool:
    return url.lower().startswith(("sqlite://", "sqlite+"))


def _allow_sqlite_database_url() -> bool:
    raw = os.getenv("ALLOW_SQLITE_DATABASE_URL", "")
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}


def _required_database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if not url:
        raise SystemExit("DATABASE_URL is not set")
    if _is_sqlite_url(url) and not _allow_sqlite_database_url():
        raise SystemExit(
            "SQLite DATABASE_URL is disabled for fix_orphans.py. "
            "Use PostgreSQL as the schema source of truth, or set "
            "ALLOW_SQLITE_DATABASE_URL=1 only for explicit legacy tools/tests."
        )
    return url


def _require_fix_orphans_confirmation() -> None:
    if os.getenv("CONFIRM_FIX_ORPHANS") != "1":
        raise SystemExit(
            "Refusing to run manual orphan repair without CONFIRM_FIX_ORPHANS=1."
        )


def main():
    try:
        _require_fix_orphans_confirmation()
        url = _required_database_url()
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    engine = sa.create_engine(url, future=True)
    applied = 0
    with engine.begin() as conn:
        for idx, sql in enumerate(SQLS, 1):
            try:
                conn.exec_driver_sql(sql)
                applied += 1
                print("[" + str(idx) + "/" + str(len(SQLS)) + "] OK")
            except Exception as e:
                print("[" + str(idx) + "/" + str(len(SQLS)) + "] WARN: " + str(e))
    print("Applied " + str(applied) + " of " + str(len(SQLS)) + " statements.")


if __name__ == "__main__":
    main()

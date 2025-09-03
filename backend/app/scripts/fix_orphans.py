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


def main():
    url = os.getenv("DATABASE_URL")
    if not url:
        print("DATABASE_URL is not set", file=sys.stderr)
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

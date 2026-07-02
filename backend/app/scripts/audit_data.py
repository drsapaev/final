#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Аудит «висячих» ссылок (orphans) и краткая статистика по ключевым связям.
Пишет CSV: backend/app/scripts/out/audit_orphans.csv
Использует DATABASE_URL из окружения.
"""
from __future__ import annotations

import os
import sys

import sqlalchemy as sa

PAIRS = [
    ("visits", "patient_id", "patients", "id"),
    ("visits", "doctor_id", "users", "id"),
    ("visit_services", "visit_id", "visits", "id"),
    ("visit_services", "service_id", "services", "id"),
    ("payments", "visit_id", "visits", "id"),
    ("payments", "patient_id", "patients", "id"),
    ("schedules", "doctor_id", "users", "id"),
    ("schedules", "patient_id", "patients", "id"),
    ("queues", "patient_id", "patients", "id"),
    ("queues", "service_id", "services", "id"),
    ("online_appointments", "patient_id", "patients", "id"),
    ("online_appointments", "doctor_id", "users", "id"),
    ("lab_results", "visit_id", "visits", "id"),
    ("audit_trail", "user_id", "users", "id"),
]

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
            "SQLite DATABASE_URL is disabled for audit_data.py. "
            "Use PostgreSQL as the schema source of truth, or set "
            "ALLOW_SQLITE_DATABASE_URL=1 only for explicit legacy tools/tests."
        )
    return url


def table_has(inspector, table: str, col: str) -> bool:
    return table in inspector.get_table_names() and any(
        c["name"] == col for c in inspector.get_columns(table)
    )


def count_orphans(conn, child_t, child_c, parent_t, parent_c="id"):
    insp = sa.inspect(conn)
    if not table_has(insp, child_t, child_c) or not table_has(insp, parent_t, parent_c):
        return None
    q = sa.text(
        f"""
        SELECT COUNT(*) AS cnt
        FROM "{child_t}" c
        LEFT JOIN "{parent_t}" p ON c."{child_c}" = p."{parent_c}"
        WHERE c."{child_c}" IS NOT NULL AND p."{parent_c}" IS NULL
    """
    )
    return conn.execute(q).scalar_one()


def main():
    try:
        url = _required_database_url()
    except SystemExit as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(2)
    engine = sa.create_engine(url, future=True)
    out_dir = os.path.join(os.path.dirname(__file__), "out")
    os.makedirs(out_dir, exist_ok=True)
    out_csv = os.path.join(out_dir, "audit_orphans.csv")
    rows = []
    with engine.connect() as conn:
        for ct, cc, pt, pc in PAIRS:
            cnt = count_orphans(conn, ct, cc, pt, pc)
            rows.append(
                {
                    "child_table": ct,
                    "child_column": cc,
                    "parent_table": pt,
                    "parent_column": pc,
                    "orphans": "n/a" if cnt is None else int(cnt),
                }
            )
    import csv as _csv

    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote: {out_csv}")


if __name__ == "__main__":
    main()

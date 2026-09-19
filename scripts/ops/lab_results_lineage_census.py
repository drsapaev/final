"""Read-only production census of lab_results lineage state (stage 4 tooling).

Owner contract: .ai-factory/plans/lab-results-lineage-decision.md — the
read-only census of historical rows is the prerequisite for any operator
decision on history repair. This script is REPRODUCIBLE evidence tooling:
it only reads, prints aggregates and technical identifiers (no patient
PII), never prints the DSN, and never modifies data.

Usage (from backend/ with the backend venv):
    LAB_LINEAGE_CENSUS_DSN=postgresql://... python \
        ../scripts/ops/lab_results_lineage_census.py

Falls back to DATABASE_URL (backend/.env or environment) when the
dedicated variable is unset. The transaction is READ ONLY with a
statement timeout and always rolls back.
"""
from __future__ import annotations

import io
import os
import sys
from pathlib import Path

import psycopg

BACKEND_ENV = Path(__file__).resolve().parents[2] / "backend" / ".env"


def load_dsn() -> str:
    dsn = os.getenv("LAB_LINEAGE_CENSUS_DSN", "").strip()
    if not dsn:
        dsn = os.getenv("DATABASE_URL", "").strip()
    if not dsn and BACKEND_ENV.exists():
        for line in io.open(BACKEND_ENV, encoding="utf-8", errors="ignore"):
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                dsn = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not dsn:
        raise SystemExit(
            "no DSN: set LAB_LINEAGE_CENSUS_DSN (preferred) or DATABASE_URL"
        )
    for prefix in ("postgresql+psycopg://", "postgresql+asyncpg://"):
        if dsn.startswith(prefix):
            dsn = dsn.replace(prefix, "postgresql://", 1)
    return dsn


def main() -> int:
    conn = psycopg.connect(load_dsn(), connect_timeout=15)
    conn.autocommit = False
    cur = conn.cursor()
    cur.execute("SET statement_timeout = '20s'")
    cur.execute("SET TRANSACTION READ ONLY")

    def one(sql: str, params: tuple | None = None):
        cur.execute(sql, params or ())
        return cur.fetchone()[0]

    def rows(sql: str, params: tuple | None = None):
        cur.execute(sql, params or ())
        return cur.fetchall()

    print("== migration state ==")
    try:
        version = one("select version_num from alembic_version")
        print("alembic_version:", version)
        print("0070 applied:", str(version).startswith("0070"))
    except Exception as exc:  # noqa: BLE001
        print("alembic_version unavailable:", type(exc).__name__)
        conn.rollback()
        cur.execute("SET statement_timeout = '20s'")
        cur.execute("SET TRANSACTION READ ONLY")

    print("\n== lineage columns ==")
    has_lineage = one(
        "select count(*) from information_schema.columns "
        "where table_name = 'lab_results' "
        "and column_name in ('source_root_instance_id','source_instance_id')"
    )
    print("lineage columns present:", has_lineage, "of 2")

    print("\n== totals ==")
    print("lab_results total:", one("select count(*) from lab_results"))
    print(
        "FINALIZED/PRINTED instances:",
        one(
            "select count(*) from lab_report_instances "
            "where status in ('FINALIZED','PRINTED')"
        ),
    )
    print(
        "distinct orders with finalized instances:",
        one(
            "select count(distinct order_id) from lab_report_instances "
            "where status in ('FINALIZED','PRINTED') and order_id is not null"
        ),
    )

    if has_lineage == 2:
        print("\n== managed (lineage) rows ==")
        print(
            "managed rows:",
            one(
                "select count(*) from lab_results "
                "where source_root_instance_id is not null"
            ),
        )

    print("\n== shared orders (>=2 finalized blanks, C/A+ ambiguity class) ==")
    total_shared = one(
        "select count(*) from ("
        "  select order_id from lab_report_instances"
        "  where status in ('FINALIZED','PRINTED') and order_id is not null"
        "  group by order_id having count(*) > 1) s"
    )
    print("orders with >1 finalized blanks:", total_shared)
    for order_id, blanks, statuses in rows(
        "select order_id, count(*) as blanks, "
        "string_agg(distinct status, ',') as statuses "
        "from lab_report_instances "
        "where status in ('FINALIZED','PRINTED') and order_id is not null "
        "group by order_id having count(*) > 1 "
        "order by blanks desc, order_id limit 25"
    ):
        lr = one(
            "select count(*) from lab_results where order_id = %s", (order_id,)
        )
        print(
            f"  order #{order_id}: finalized_blanks={blanks} "
            f"statuses={statuses} lab_results_rows={lr}"
        )

    print("\n== projected coverage on shared orders ==")
    covered = one(
        "select count(*) from ("
        "  select s.order_id from ("
        "    select order_id from lab_report_instances"
        "    where status in ('FINALIZED','PRINTED') and order_id is not null"
        "    group by order_id having count(*) > 1) s"
        "  join lab_results lr on lr.order_id = s.order_id"
        "  group by s.order_id) c"
    )
    print("shared orders having ANY legacy rows:", covered)
    print(
        "shared orders with NO legacy rows (C-era skip victims):",
        total_shared - covered,
    )

    print("\n== duplicate (order_id, test_code) pairs in lab_results ==")
    print(
        "duplicate groups:",
        one(
            "select count(*) from ("
            "  select order_id, test_code from lab_results"
            "  where test_code is not null"
            "  group by order_id, test_code having count(*) > 1) d"
        ),
    )
    for order_id, code, n in rows(
        "select order_id, test_code, count(*) as n from lab_results "
        "where test_code is not null "
        "group by order_id, test_code having count(*) > 1 "
        "order by n desc, order_id, test_code limit 15"
    ):
        print(f"  order #{order_id} test_code={code}: {n} rows")

    print("\n== cross-template collision exposure (biochem_panel x urinalysis_oam) ==")
    try:
        print(
            "orders finalizing BOTH colliding templates:",
            one(
                "select count(*) from ("
                "  select ri.order_id from lab_report_instances ri"
                "  join lab_report_templates t on t.id = ri.template_id"
                "  where ri.status in ('FINALIZED','PRINTED') and ri.order_id is not null"
                "    and t.code in ('biochem_panel','urinalysis_oam')"
                "  group by ri.order_id"
                "  having count(distinct t.code) = 2) c"
            ),
        )
    except Exception as exc:  # noqa: BLE001
        print("collision query unavailable:", type(exc).__name__)

    conn.rollback()
    conn.close()
    print("\nREAD ONLY transaction rolled back. No data was modified.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

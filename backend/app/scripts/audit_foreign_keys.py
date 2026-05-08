#!/usr/bin/env python3
"""Audit foreign keys and orphaned records for the configured database."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import sqlalchemy as sa
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))


def get_database_url() -> str:
    url = os.getenv("DATABASE_URL")
    if url and url.strip():
        return url.strip()

    settings_error = None
    try:
        from app.core.config import settings

        settings_url = getattr(settings, "DATABASE_URL", None)
        if settings_url:
            return str(settings_url).strip()
    except Exception as exc:
        settings_error = exc

    raise SystemExit(
        "DATABASE_URL is required; refusing to audit a fallback database"
    ) from settings_error


def normalize_sync_database_url(url: str) -> str:
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def is_sqlite_database_url(url: str) -> bool:
    return make_url(url).drivername.startswith("sqlite")


def allow_sqlite_database_url() -> bool:
    raw = os.getenv("ALLOW_SQLITE_DATABASE_URL", "")
    if raw.strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}


def enforce_database_url_policy(url: str) -> None:
    if is_sqlite_database_url(url) and not allow_sqlite_database_url():
        raise SystemExit(
            "SQLite DATABASE_URL is disabled for audit_foreign_keys.py. "
            "Use PostgreSQL as the schema source of truth, or set "
            "ALLOW_SQLITE_DATABASE_URL=1 only for explicit legacy tools/tests."
        )


def display_database_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def get_foreign_keys(conn, table_name: str) -> List[Dict[str, Any]]:
    """Return foreign keys for one table, or an empty list if inspection fails."""
    inspector = inspect(conn)
    try:
        return inspector.get_foreign_keys(table_name)
    except Exception:
        return []


def check_orphaned_records(
    conn,
    child_table: str,
    fk_column: str,
    parent_table: str,
    parent_pk: str = "id",
) -> int:
    """Return the orphaned-row count for one FK relationship."""
    try:
        query = text(
            f"""
            SELECT COUNT(*) as count
            FROM "{child_table}" c
            LEFT JOIN "{parent_table}" p ON c."{fk_column}" = p."{parent_pk}"
            WHERE c."{fk_column}" IS NOT NULL AND p."{parent_pk}" IS NULL
            """
        )
        result = conn.execute(query).fetchone()
        return result[0] if result else 0
    except Exception as exc:
        print(
            "  [WARNING] Could not check "
            f"{child_table}.{fk_column} -> {parent_table}.{parent_pk}: {exc}"
        )
        return -1


def audit_all_foreign_keys(conn) -> Dict[str, Any]:
    """Audit all FK relationships and orphaned records in the database."""
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    results: Dict[str, Any] = {
        "total_tables": len(tables),
        "tables_with_fks": 0,
        "total_fks": 0,
        "orphaned_records": [],
        "errors": [],
    }

    print("=" * 80)
    print("FOREIGN KEY AND ORPHANED RECORD AUDIT")
    print("=" * 80)
    print()

    for table in tables:
        fks = get_foreign_keys(conn, table)
        if not fks:
            continue

        results["tables_with_fks"] += 1
        results["total_fks"] += len(fks)

        print(f"Table: {table}")
        for fk in fks:
            constrained_columns = fk.get("constrained_columns", [])
            referred_table = fk.get("referred_table", "")
            referred_columns = fk.get("referred_columns", [])

            if not constrained_columns or not referred_table:
                continue

            fk_column = constrained_columns[0]
            parent_pk = referred_columns[0] if referred_columns else "id"

            print(f"  FK: {fk_column} -> {referred_table}.{parent_pk}")

            orphan_count = check_orphaned_records(
                conn,
                table,
                fk_column,
                referred_table,
                parent_pk,
            )

            if orphan_count > 0:
                results["orphaned_records"].append(
                    {
                        "table": table,
                        "column": fk_column,
                        "parent_table": referred_table,
                        "parent_pk": parent_pk,
                        "count": orphan_count,
                    }
                )
                print(f"    [ERROR] Found {orphan_count} orphaned records")
            elif orphan_count == 0:
                print("    [OK] No orphaned records")
            else:
                results["errors"].append(
                    {
                        "table": table,
                        "column": fk_column,
                        "error": "Check failed",
                    }
                )

        print()

    return results


def enable_sqlite_foreign_keys(conn, url: str) -> None:
    if not is_sqlite_database_url(url):
        return

    conn.execute(text("PRAGMA foreign_keys=ON"))
    print("[OK] Foreign key enforcement enabled for SQLite\n")

    fk_status = conn.execute(text("PRAGMA foreign_keys")).fetchone()
    if fk_status and fk_status[0]:
        print("[OK] Foreign keys are enabled in SQLite\n")
    else:
        print("[WARNING] Foreign keys are not enabled in SQLite\n")


def main() -> int:
    url = normalize_sync_database_url(get_database_url())
    enforce_database_url_policy(url)
    print(f"Database URL: {display_database_url(url)}")

    engine = sa.create_engine(url, future=True)

    with engine.connect() as conn:
        enable_sqlite_foreign_keys(conn, url)
        results = audit_all_foreign_keys(conn)

    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total tables: {results['total_tables']}")
    print(f"Tables with FK: {results['tables_with_fks']}")
    print(f"Total FK: {results['total_fks']}")
    print(f"Orphaned relationship findings: {len(results['orphaned_records'])}")
    print(f"Errors: {len(results['errors'])}")
    print()

    if results["orphaned_records"]:
        print("[WARNING] Orphaned records found:")
        for orphan in results["orphaned_records"]:
            print(
                f"  - {orphan['table']}.{orphan['column']} -> "
                f"{orphan['parent_table']}.{orphan['parent_pk']}: "
                f"{orphan['count']} records"
            )
        print()
        print("Recommendation: fix orphaned records before enabling FK enforcement.")
        return 1

    print("[OK] No orphaned records found.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

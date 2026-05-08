#!/usr/bin/env python3
"""Audit cascade-delete strategies for configured database constraints."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Dict, List

import sqlalchemy as sa
from sqlalchemy import inspect
from sqlalchemy.engine import make_url

BACKEND_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND_DIR))


CRITICAL_RELATIONSHIPS = {
    ("users", "refresh_tokens", "user_id"): "CASCADE",
    ("users", "user_sessions", "user_id"): "CASCADE",
    ("users", "password_reset_tokens", "user_id"): "CASCADE",
    ("users", "email_verification_tokens", "user_id"): "CASCADE",
    ("users", "login_attempts", "user_id"): "CASCADE",
    ("users", "user_activities", "user_id"): "CASCADE",
    ("users", "security_events", "user_id"): "CASCADE",
    ("visits", "visit_services", "visit_id"): "CASCADE",
    ("visits", "prescriptions", "visit_id"): "CASCADE",
    ("visits", "emr", "visit_id"): "SET NULL",
    ("payments", "payment_transactions", "payment_id"): "CASCADE",
    ("payments", "payment_webhooks", "payment_id"): "SET NULL",
    ("departments", "department_services", "department_id"): "CASCADE",
    ("departments", "department_queue_settings", "department_id"): "CASCADE",
    ("departments", "department_registration_settings", "department_id"): "CASCADE",
    ("files", "file_versions", "file_id"): "CASCADE",
    ("files", "file_shares", "file_id"): "CASCADE",
    ("daily_queues", "online_queue_entries", "queue_id"): "CASCADE",
}

PRESERVE_RELATIONSHIPS = {
    ("patients", "visits", "patient_id"): "SET NULL",
    ("patients", "appointments", "patient_id"): "SET NULL",
    ("users", "visits", "doctor_id"): "SET NULL",
    ("users", "appointments", "doctor_id"): "SET NULL",
}


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
            "SQLite DATABASE_URL is disabled for audit_cascade_deletes.py. "
            "Use PostgreSQL as the schema source of truth, or set "
            "ALLOW_SQLITE_DATABASE_URL=1 only for explicit legacy tools/tests."
        )


def display_database_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def audit_cascade_strategies(conn) -> Dict[str, List[Dict]]:
    """Audit cascade strategies in database foreign key metadata."""
    inspector = inspect(conn)
    tables = inspector.get_table_names()

    results = {
        "missing_cascade": [],
        "inconsistent_cascade": [],
        "orphan_risk": [],
        "safe_cascade": [],
    }

    print("=" * 80)
    print("CASCADE DELETE STRATEGY AUDIT")
    print("=" * 80)
    print()

    for table in tables:
        try:
            fks = inspector.get_foreign_keys(table)
        except Exception as exc:
            print(f"[WARNING] Could not inspect table {table}: {exc}")
            continue

        for fk in fks:
            constrained_columns = fk.get("constrained_columns", [])
            referred_table = fk.get("referred_table", "")
            fk_name = fk.get("name", "unnamed")

            if not constrained_columns or not referred_table:
                continue

            constrained_col = constrained_columns[0]
            key = (referred_table, table, constrained_col)
            ondelete = fk.get("options", {}).get("ondelete")

            expected_cascade = CRITICAL_RELATIONSHIPS.get(key)
            should_preserve = PRESERVE_RELATIONSHIPS.get(key)

            if expected_cascade:
                if ondelete != expected_cascade:
                    results["inconsistent_cascade"].append(
                        {
                            "table": table,
                            "column": constrained_col,
                            "parent_table": referred_table,
                            "current": ondelete or "NONE",
                            "expected": expected_cascade,
                            "fk_name": fk_name,
                        }
                    )
                    print(f"[WARNING] {table}.{constrained_col} -> {referred_table}")
                    print(f"     Current: {ondelete or 'NONE'}, expected: {expected_cascade}")
                else:
                    results["safe_cascade"].append(
                        {
                            "table": table,
                            "column": constrained_col,
                            "parent_table": referred_table,
                            "cascade": ondelete,
                        }
                    )
                    print(f"[OK] {table}.{constrained_col} -> {referred_table}: {ondelete}")

            elif should_preserve:
                if ondelete and ondelete != "SET NULL":
                    results["orphan_risk"].append(
                        {
                            "table": table,
                            "column": constrained_col,
                            "parent_table": referred_table,
                            "current": ondelete,
                            "recommended": "SET NULL",
                            "reason": "Data should be preserved",
                        }
                    )
                    print(f"[WARNING] {table}.{constrained_col} -> {referred_table}")
                    print(f"     Current: {ondelete}, recommended: SET NULL")

            elif not ondelete and referred_table in {"users", "patients", "visits", "payments"}:
                results["missing_cascade"].append(
                    {
                        "table": table,
                        "column": constrained_col,
                        "parent_table": referred_table,
                        "fk_name": fk_name,
                    }
                )
                print(f"[ERROR] {table}.{constrained_col} -> {referred_table}: no cascade")

    return results


def main() -> int:
    url = normalize_sync_database_url(get_database_url())
    enforce_database_url_policy(url)
    print(f"Database URL: {display_database_url(url)}")

    engine = sa.create_engine(url, future=True)
    with engine.connect() as conn:
        results = audit_cascade_strategies(conn)

    print()
    print("=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"[OK] Safe cascade policies: {len(results['safe_cascade'])}")
    print(f"[WARNING] Inconsistent policies: {len(results['inconsistent_cascade'])}")
    print(f"[ERROR] Missing cascade policies: {len(results['missing_cascade'])}")
    print(f"[WARNING] Data preservation risks: {len(results['orphan_risk'])}")
    print()

    if results["inconsistent_cascade"] or results["missing_cascade"]:
        print("[WARNING] Cascade delete issues found.")
        return 1

    print("[OK] Cascade delete strategies are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env python3
"""Verify SQLite foreign-key enforcement for local diagnostic databases.

Runtime PostgreSQL integrity is governed by the database engine, SQLAlchemy
models, and Alembic migrations. This helper intentionally avoids pretending that
SQLite PRAGMA checks validate non-SQLite databases.

Exit codes:
  0 = SQLite FK enforcement works, or the configured database is non-SQLite
  1 = SQLite FK enforcement is disabled
  2 = configuration, connection, or verification error
  3 = SQLite FK violation test did not fail
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

try:
    from sqlalchemy import create_engine, event, text
    from sqlalchemy.engine import make_url
    from sqlalchemy.exc import IntegrityError
except ImportError as exc:
    print(f"ERROR: Failed to import SQLAlchemy: {exc}", file=sys.stderr)
    sys.exit(2)


def get_database_url() -> str:
    """Read DATABASE_URL from env/settings and refuse implicit fallbacks."""
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

    raise RuntimeError(
        "DATABASE_URL is required; refusing to verify a fallback database"
    ) from settings_error


def normalize_sync_database_url(url: str) -> str:
    """Convert async SQLite URLs to sync URLs for this diagnostic helper."""
    if url.startswith("sqlite+aiosqlite://"):
        return url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return url


def is_sqlite_database_url(url: str) -> bool:
    return make_url(url).drivername.startswith("sqlite")


def display_database_url(url: str) -> str:
    return make_url(url).render_as_string(hide_password=True)


def require_sqlite_fk_write_test_confirmation() -> None:
    if os.getenv("CONFIRM_VERIFY_SQLITE_FK_WRITE_TEST") != "1":
        raise RuntimeError(
            "Refusing to run SQLite FK write test. "
            "It intentionally inserts a violating row to verify enforcement. "
            "Set CONFIRM_VERIFY_SQLITE_FK_WRITE_TEST=1 only for an explicit local diagnostic run."
        )


def _print_header(url: str) -> None:
    print("=" * 80)
    print("FOREIGN KEY ENFORCEMENT VERIFICATION")
    print("=" * 80)
    print(f"Database URL: {display_database_url(url)}")
    print()


def _enable_sqlite_fk(dbapi_conn, connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def verify_fk_enforcement() -> int:
    """Return an exit code describing the FK verification result."""
    try:
        url = normalize_sync_database_url(get_database_url())
    except Exception as exc:
        print("=" * 80)
        print("DATABASE CONFIGURATION ERROR")
        print("=" * 80)
        print(f"Error: {exc}")
        print()
        return 2

    _print_header(url)

    if not is_sqlite_database_url(url):
        print("This helper is SQLite-specific.")
        print("Foreign key enforcement is managed by the configured database engine.")
        print("Use Alembic and production readiness checks for cross-database validation.")
        print()
        return 0

    try:
        require_sqlite_fk_write_test_confirmation()
    except Exception as exc:
        print(f"Error: {exc}")
        print()
        return 2

    try:
        engine = create_engine(url, future=True, pool_pre_ping=True)
        event.listen(engine, "connect", _enable_sqlite_fk)

        with engine.connect() as conn:
            print("Step 1: Checking PRAGMA foreign_keys status...")
            conn.execute(text("PRAGMA foreign_keys=ON"))
            result = conn.execute(text("PRAGMA foreign_keys")).scalar()
            print(f"   PRAGMA foreign_keys = {result}")

            if result != 1:
                print()
                print("=" * 80)
                print("CRITICAL ERROR: Foreign key enforcement is DISABLED!")
                print("=" * 80)
                print(f"   PRAGMA foreign_keys returned {result} instead of 1")
                print("   This means foreign key constraints are NOT being enforced.")
                print("   Medical data integrity verification failed.")
                print()
                return 1

            print("   Foreign key enforcement is ENABLED")
            print()

            print("Step 2: Testing FK enforcement with violation attempt...")
            try:
                conn.execute(
                    text(
                        """
                        INSERT INTO visits (patient_id, status, created_at)
                        VALUES (999999999, 'test', datetime('now'))
                        """
                    )
                )
                conn.commit()
            except IntegrityError:
                print("   FK violation correctly rejected.")
                conn.rollback()
            except Exception as exc:
                error_msg = str(exc).lower()
                conn.rollback()
                if "foreign key" in error_msg or "constraint" in error_msg:
                    print(f"   FK violation correctly rejected: {type(exc).__name__}")
                else:
                    print(f"   Verification could not complete: {exc}")
                    return 2
            else:
                print("   CRITICAL: FK violation test did NOT fail.")
                try:
                    conn.execute(text("DELETE FROM visits WHERE patient_id = 999999999"))
                    conn.commit()
                except Exception:
                    conn.rollback()
                return 3

            print()
            print("=" * 80)
            print("VERIFICATION PASSED")
            print("=" * 80)
            print("SQLite foreign key enforcement is working correctly.")
            print()
            return 0

    except Exception as exc:
        print()
        print("=" * 80)
        print("DATABASE CONNECTION ERROR")
        print("=" * 80)
        print(f"Error: {exc}")
        print()
        return 2


if __name__ == "__main__":
    sys.exit(verify_fk_enforcement())

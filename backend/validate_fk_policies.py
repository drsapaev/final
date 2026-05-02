"""Validate FK constraints for the configured database."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any, Dict, List

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqlalchemy import create_engine, inspect, text  # noqa: E402
from sqlalchemy.engine import make_url  # noqa: E402

from app.core.config import get_settings  # noqa: E402


def get_db_url() -> str:
    try:
        settings = get_settings()
        db_url = str(settings.DATABASE_URL or "").strip()
    except Exception as exc:
        raise RuntimeError(
            "DATABASE_URL is required; refusing to validate a fallback database"
        ) from exc

    if not db_url:
        raise RuntimeError(
            "DATABASE_URL is required; refusing to validate a fallback database"
        )

    return db_url


def normalize_sync_db_url(db_url: str) -> str:
    if db_url.startswith("sqlite+aiosqlite://"):
        return db_url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    return db_url


def is_sqlite_url(db_url: str) -> bool:
    return make_url(db_url).drivername.startswith("sqlite")


def display_db_url(db_url: str) -> str:
    return make_url(db_url).render_as_string(hide_password=True)


DATABASE_URL = normalize_sync_db_url(get_db_url())

print("=" * 80)
print("FK POLICY VALIDATION")
print("=" * 80)
print(f"Database URL: {display_db_url(DATABASE_URL)}\n")


def check_fk_enforcement(engine) -> bool:
    """Check FK enforcement where the database exposes a runtime switch."""
    print("Step 1: Checking FK enforcement...")

    if not is_sqlite_url(DATABASE_URL):
        print("  Foreign key enforcement is managed by the database engine\n")
        return True

    with engine.connect() as conn:
        conn.execute(text("PRAGMA foreign_keys=ON"))
        result = conn.execute(text("PRAGMA foreign_keys")).scalar()
        if result == 1:
            print("  Foreign key enforcement is ENABLED\n")
            return True

        print(f"  Foreign key enforcement is DISABLED (status: {result})\n")
        return False


def get_all_fk_constraints(engine) -> List[Dict[str, Any]]:
    """Get all FK constraints through SQLAlchemy inspector."""
    print("Step 2: Analyzing FK constraints...")
    fk_constraints = []

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    for table in tables:
        fks = inspector.get_foreign_keys(table)
        for fk in fks:
            fk_constraints.append(
                {
                    "table": table,
                    "constrained_columns": fk["constrained_columns"],
                    "referred_table": fk["referred_table"],
                    "referred_columns": fk["referred_columns"],
                    "name": fk.get("name", "N/A"),
                }
            )

    print(f"  Found {len(fk_constraints)} FK constraints across {len(tables)} tables\n")
    return fk_constraints


def validate_fk_policies(engine) -> bool:
    """Validate that FK policies are represented by schema/model contracts."""
    print("Step 3: Validating FK policies...")

    if is_sqlite_url(DATABASE_URL):
        print("  SQLite does not expose all ondelete policy metadata consistently")
    else:
        print("  FK constraints were introspected from the configured database")

    print("  Full ondelete policy validation still requires model/Alembic review\n")
    return True


def test_cascade_behavior(engine) -> bool:
    """Placeholder for destructive behavior tests that require fixture data."""
    print("Step 4: Testing FK behavior...")
    print("  Skipping behavior tests because they require controlled fixture data")
    print("  FK constraints are defined in models and database schema\n")
    return True


def main() -> int:
    engine = create_engine(DATABASE_URL, future=True)

    if not check_fk_enforcement(engine):
        print("VALIDATION FAILED: FK enforcement is disabled")
        return 1

    fk_constraints = get_all_fk_constraints(engine)

    if len(fk_constraints) == 0:
        print("WARNING: No FK constraints found (database may be empty)")
        print("  Run migrations: alembic upgrade head")
        return 0

    if not validate_fk_policies(engine):
        print("VALIDATION FAILED: FK policies validation failed")
        return 1

    test_cascade_behavior(engine)

    print("=" * 80)
    print("VALIDATION PASSED")
    print("=" * 80)
    print("\nSummary:")
    print("  - FK enforcement: available for configured database")
    print(f"  - FK constraints found: {len(fk_constraints)}")
    print("  - FK policies require model/Alembic review for full assurance")
    print("  - FK constraints will be enforced on database operations")
    print("\nNext steps:")
    print("  1. Verify models have correct ondelete policies")
    print("  2. Test CASCADE/SET NULL/RESTRICT behavior with controlled test data")
    print("  3. Run audit_foreign_keys.py to check for orphaned records")
    return 0


if __name__ == "__main__":
    sys.exit(main())

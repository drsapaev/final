"""
Скрипт для удаления orphaned записей из базы данных.
Использует SET NULL политики для безопасного очищения.
"""
import os
import sys
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

# Add backend to sys.path
sys.path.insert(0, os.path.abspath(os.path.dirname(__file__)))

from app.core.config import get_settings


def _is_sqlite_url(url: str) -> bool:
    return url.lower().startswith(("sqlite://", "sqlite+"))


def _safe_database_url_for_log(url: str) -> str:
    try:
        return make_url(url).render_as_string(hide_password=True)
    except Exception:
        return "<invalid database url>"


def get_db_url():
    try:
        settings = get_settings()
    except Exception as exc:
        raise RuntimeError(
            "DATABASE_URL must be configured before orphan cleanup."
        ) from exc

    db_url = str(getattr(settings, "DATABASE_URL", "") or "").strip()
    if not db_url:
        raise RuntimeError("DATABASE_URL must be configured before orphan cleanup.")
    if _is_sqlite_url(db_url):
        raise RuntimeError(
            "SQLite DATABASE_URL is disabled for orphan cleanup. "
            "Use PostgreSQL as the database source of truth; use explicit "
            "legacy migration/recovery tools for SQLite snapshots."
        )
    return db_url

DATABASE_URL = get_db_url()

print("=" * 80)
print("CLEANUP ORPHANED RECORDS")
print("=" * 80)
print(f"Database URL: {_safe_database_url_for_log(DATABASE_URL)}\n")

# Orphaned records cleanup strategies
CLEANUP_STRATEGIES = {
    # DELETE where NOT NULL constraint exists
    "daily_queues": {
        "specialist_id": "DELETE",  # Queue requires specialist, delete if orphaned
    },
    # SET NULL where nullable (will auto-detect NOT NULL and use DELETE)
    "emr": {
        "appointment_id": "SET NULL",  # EMR preserved, appointment_id set to NULL (if nullable)
    },
    "file_folders": {
        "owner_id": "SET NULL",  # Folder preserved, owner_id set to NULL
    },
    "queue_tokens": {
        "specialist_id": "SET NULL",  # Token preserved (nullable)
        "generated_by_user_id": "SET NULL",  # Token preserved (nullable)
    },
    "visits": {
        "doctor_id": "SET NULL",  # Visit preserved, doctor_id set to NULL (nullable)
    },
    "role_permissions": {
        "role_id": "DELETE",  # Invalid M2M relationship, delete
    },
}

def cleanup_orphaned_records(engine):
    """Clean up orphaned records according to FK policies"""
    print("Step 1: Identifying orphaned records...\n")
    
    inspector = inspect(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    total_cleaned = 0
    
    try:
        for table_name, columns in CLEANUP_STRATEGIES.items():
            if table_name not in inspector.get_table_names():
                continue
                
            print(f"📋 Table: {table_name}")
            
            for column_name, strategy in columns.items():
                # Check if column exists
                columns_info = inspector.get_columns(table_name)
                if not any(col['name'] == column_name for col in columns_info):
                    continue
                
                # Find orphaned records
                # Get FK info
                fks = inspector.get_foreign_keys(table_name)
                fk_info = None
                for fk in fks:
                    if column_name in fk['constrained_columns']:
                        fk_info = fk
                        break
                
                if not fk_info:
                    continue
                
                referred_table = fk_info['referred_table']
                referred_column = fk_info['referred_columns'][0]
                
                # Count orphaned records
                count_query = text(f"""
                    SELECT COUNT(*) as count
                    FROM {table_name} c
                    LEFT JOIN {referred_table} p ON c.{column_name} = p.{referred_column}
                    WHERE c.{column_name} IS NOT NULL AND p.{referred_column} IS NULL
                """)
                
                result = session.execute(count_query).fetchone()
                orphaned_count = result[0] if result else 0
                
                if orphaned_count == 0:
                    print(f"  ✅ {column_name}: No orphaned records")
                    continue
                
                print(f"  🔧 {column_name}: Found {orphaned_count} orphaned records")
                
                if strategy == "SET NULL":
                    # Check if column is nullable
                    columns_info = inspector.get_columns(table_name)
                    column_info = next((col for col in columns_info if col['name'] == column_name), None)
                    is_nullable = column_info and column_info.get('nullable', False)
                    
                    if not is_nullable:
                        # Column is NOT NULL, use DELETE instead
                        print(f"     ⚠️  Column is NOT NULL, using DELETE strategy instead")
                        delete_query = text(f"""
                            DELETE FROM {table_name}
                            WHERE {column_name} IS NOT NULL
                            AND NOT EXISTS (
                                SELECT 1 FROM {referred_table} p
                                WHERE p.{referred_column} = {table_name}.{column_name}
                            )
                        """)
                        result = session.execute(delete_query)
                        affected = result.rowcount
                        session.commit()
                        print(f"     ✅ Deleted {affected} orphaned records")
                        total_cleaned += affected
                    else:
                        # Set FK to NULL
                        update_query = text(f"""
                            UPDATE {table_name}
                            SET {column_name} = NULL
                            WHERE {column_name} IS NOT NULL
                            AND NOT EXISTS (
                                SELECT 1 FROM {referred_table} p
                                WHERE p.{referred_column} = {table_name}.{column_name}
                            )
                        """)
                        result = session.execute(update_query)
                        affected = result.rowcount
                        session.commit()
                        print(f"     ✅ Set {affected} records to NULL")
                        total_cleaned += affected
                    
                elif strategy == "DELETE":
                    # Delete orphaned records
                    delete_query = text(f"""
                        DELETE FROM {table_name}
                        WHERE {column_name} IS NOT NULL
                        AND NOT EXISTS (
                            SELECT 1 FROM {referred_table} p
                            WHERE p.{referred_column} = {table_name}.{column_name}
                        )
                    """)
                    result = session.execute(delete_query)
                    affected = result.rowcount
                    session.commit()
                    print(f"     ✅ Deleted {affected} orphaned records")
                    total_cleaned += affected
                    
            print()
            
        print("=" * 80)
        print(f"✅ CLEANUP COMPLETE: {total_cleaned} records cleaned")
        print("=" * 80)
        
    except Exception as e:
        session.rollback()
        print(f"\n❌ ERROR during cleanup: {e}")
        raise
    finally:
        session.close()

def verify_cleanup(engine):
    """Verify that no orphaned records remain"""
    print("\nStep 2: Verifying cleanup...\n")
    
    inspector = inspect(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    orphaned_found = False
    
    try:
        for table_name, columns in CLEANUP_STRATEGIES.items():
            if table_name not in inspector.get_table_names():
                continue
                
            for column_name in columns.keys():
                # Get FK info
                fks = inspector.get_foreign_keys(table_name)
                fk_info = None
                for fk in fks:
                    if column_name in fk['constrained_columns']:
                        fk_info = fk
                        break
                
                if not fk_info:
                    continue
                
                referred_table = fk_info['referred_table']
                referred_column = fk_info['referred_columns'][0]
                
                # Check for remaining orphaned records
                count_query = text(f"""
                    SELECT COUNT(*) as count
                    FROM {table_name} c
                    LEFT JOIN {referred_table} p ON c.{column_name} = p.{referred_column}
                    WHERE c.{column_name} IS NOT NULL AND p.{referred_column} IS NULL
                """)
                
                result = session.execute(count_query).fetchone()
                count = result[0] if result else 0
                
                if count > 0:
                    print(f"  ⚠️  {table_name}.{column_name}: Still {count} orphaned records")
                    orphaned_found = True
                else:
                    print(f"  ✅ {table_name}.{column_name}: Clean")
                    
    finally:
        session.close()
    
    if orphaned_found:
        print("\n⚠️  WARNING: Some orphaned records remain")
        return False
    else:
        print("\n✅ VERIFICATION PASSED: No orphaned records found")
        return True

def main():
    engine = create_engine(DATABASE_URL, future=True)

    # Cleanup orphaned records
    cleanup_orphaned_records(engine)
    
    # Verify cleanup
    if verify_cleanup(engine):
        print("\n" + "=" * 80)
        print("✅ DATABASE IS CLEAN")
        print("=" * 80)
        sys.exit(0)
    else:
        print("\n" + "=" * 80)
        print("⚠️  DATABASE CLEANUP INCOMPLETE")
        print("=" * 80)
        sys.exit(1)

if __name__ == "__main__":
    main()


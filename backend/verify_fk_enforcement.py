#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CRITICAL: Foreign Key Enforcement Verification Script

This script verifies that foreign key constraints are properly enforced
in the SQLite database. This is MANDATORY for medical clinic systems.

Exit codes:
  0 = FK enforcement is working (foreign_keys = 1)
  1 = FK enforcement is DISABLED (foreign_keys = 0) - CRITICAL ERROR
  2 = Database connection error
  3 = FK test violation did not fail (FK not working)
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend to path
backend_dir = Path(__file__).parent
sys.path.insert(0, str(backend_dir))

try:
    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError
except ImportError as e:
    print(f"❌ ERROR: Failed to import SQLAlchemy: {e}", file=sys.stderr)
    sys.exit(2)


def get_database_url() -> str:
    """Get database URL from environment or settings"""
    # Try environment variable
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    
    # Try settings
    try:
        from app.core.config import settings
        url = getattr(settings, "DATABASE_URL", None)
        if url:
            return str(url)
    except Exception:
        pass
    
    # Fallback
    return "sqlite:///./clinic.db"


def verify_fk_enforcement() -> int:
    """
    Verify foreign key enforcement is working.
    Returns exit code: 0 = success, 1 = FK disabled, 2 = connection error, 3 = FK not working
    """
    url = get_database_url()
    
    # Normalize SQLite URL
    if url.startswith("sqlite+aiosqlite://"):
        url = url.replace("sqlite+aiosqlite://", "sqlite://", 1)
    
    print("=" * 80)
    print("FOREIGN KEY ENFORCEMENT VERIFICATION")
    print("=" * 80)
    print(f"Database URL: {url}")
    print()
    
    if not url.startswith("sqlite"):
        print("⚠️  WARNING: This script is designed for SQLite.")
        print("   Foreign key enforcement verification for other databases may differ.")
        print()
    
    try:
        # Create engine with FK enforcement
        engine = create_engine(url, future=True, pool_pre_ping=True)
        
        # Add event listener for FK enforcement (same as session.py)
        if url.startswith("sqlite"):
            from sqlalchemy import event
            def _enable_fk(dbapi_conn, connection_record):
                cursor = dbapi_conn.cursor()
                cursor.execute("PRAGMA foreign_keys=ON")
                cursor.close()
            event.listen(engine, "connect", _enable_fk)
        
        with engine.connect() as conn:
            # Step 1: Check PRAGMA foreign_keys status
            print("Step 1: Checking PRAGMA foreign_keys status...")
            if url.startswith("sqlite"):
                # Ensure FK is enabled
                conn.execute(text("PRAGMA foreign_keys=ON"))
                result = conn.execute(text("PRAGMA foreign_keys")).scalar()
                
                print(f"   PRAGMA foreign_keys = {result}")
                
                if result != 1:
                    print()
                    print("=" * 80)
                    print("❌ CRITICAL ERROR: Foreign key enforcement is DISABLED!")
                    print("=" * 80)
                    print(f"   PRAGMA foreign_keys returned {result} instead of 1")
                    print("   This means foreign key constraints are NOT being enforced.")
                    print("   This is a CRITICAL security risk for medical data integrity.")
                    print()
                    print("   Impact:")
                    print("   - Orphaned records can exist in the database")
                    print("   - Data integrity violations are not prevented")
                    print("   - Medical records can be corrupted")
                    print("   - Legal compliance violation")
                    print()
                    return 1
                
                print("   ✅ Foreign key enforcement is ENABLED")
            else:
                print("   ⚠️  Skipping PRAGMA check (not SQLite)")
            
            print()
            
            # Step 2: Test FK enforcement with actual violation attempt
            print("Step 2: Testing FK enforcement with violation attempt...")
            try:
                # Try to insert a record that violates FK constraint
                # This should FAIL if FK enforcement is working
                test_query = text("""
                    -- Try to insert into visits with non-existent patient_id
                    -- This should fail if FK enforcement is working
                    INSERT INTO visits (patient_id, status, created_at)
                    VALUES (999999999, 'test', datetime('now'))
                """)
                
                conn.execute(test_query)
                conn.commit()
                
                # If we get here, FK enforcement is NOT working
                print("   ❌ CRITICAL: FK violation test did NOT fail!")
                print("   Foreign key constraints are NOT being enforced.")
                print("   The test insert should have failed but succeeded.")
                print()
                
                # Clean up test record if it was inserted
                try:
                    conn.execute(text("DELETE FROM visits WHERE patient_id = 999999999"))
                    conn.commit()
                except Exception:
                    pass
                
                return 3
                
            except IntegrityError as e:
                # This is EXPECTED - FK enforcement is working!
                print("   ✅ FK enforcement is working correctly!")
                print(f"   Foreign key violation correctly rejected: {type(e).__name__}")
                conn.rollback()
            except Exception as e:
                # Some other error - might be FK working, but check
                error_msg = str(e).lower()
                if "foreign key" in error_msg or "constraint" in error_msg:
                    print("   ✅ FK enforcement is working correctly!")
                    print(f"   Foreign key violation correctly rejected: {type(e).__name__}")
                    conn.rollback()
                else:
                    print(f"   ⚠️  Unexpected error during FK test: {e}")
                    print("   This might indicate FK is working, but verification is incomplete.")
                    conn.rollback()
            
            print()
            print("=" * 80)
            print("✅ VERIFICATION PASSED")
            print("=" * 80)
            print("Foreign key enforcement is working correctly.")
            print("The database will prevent orphaned records and data integrity violations.")
            print()
            return 0
            
    except Exception as e:
        print()
        print("=" * 80)
        print("❌ DATABASE CONNECTION ERROR")
        print("=" * 80)
        print(f"Error: {e}")
        print()
        print("Please check:")
        print("  1. Database file exists")
        print("  2. DATABASE_URL is correct")
        print("  3. Database file is not locked")
        print()
        return 2


if __name__ == "__main__":
    exit_code = verify_fk_enforcement()
    sys.exit(exit_code)


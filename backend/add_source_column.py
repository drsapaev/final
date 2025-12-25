#!/usr/bin/env python
"""Add source column to visits table for SSOT migration"""
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Check if column exists
cursor.execute("PRAGMA table_info(visits)")
columns = [col[1] for col in cursor.fetchall()]

if 'source' in columns:
    print("Column 'source' already exists")
else:
    cursor.execute("ALTER TABLE visits ADD COLUMN source VARCHAR(20) DEFAULT 'desk'")
    conn.commit()
    print("Column 'source' added successfully")

    # Update source for QR entries
    cursor.execute("""
        UPDATE visits 
        SET source = 'online' 
        WHERE id IN (
            SELECT DISTINCT visit_id 
            FROM queue_entries 
            WHERE visit_id IS NOT NULL 
              AND source IN ('online', 'confirmation', 'telegram')
        )
    """)
    conn.commit()
    print(f"Updated {cursor.rowcount} rows to source='online'")

conn.close()
print("Done!")

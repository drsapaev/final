"""Fix alembic version to match current head"""
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Update to current head
cursor.execute("UPDATE alembic_version SET version_num = '20251228_0001_unique_queue_tag'")
conn.commit()

# Verify
cursor.execute("SELECT * FROM alembic_version")
print(f"Updated alembic_version to: {cursor.fetchall()}")

conn.close()
print("Done!")

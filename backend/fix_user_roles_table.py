"""Fix user_roles table structure

The existing user_roles table has wrong structure (stores role definitions instead of user-role associations).
This script:
1. Renames old user_roles to user_roles_legacy
2. Creates new user_roles as association table
"""
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

try:
    # 1. Check if user_roles_legacy already exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='user_roles_legacy'")
    if cursor.fetchone():
        print("user_roles_legacy already exists, dropping it first")
        cursor.execute("DROP TABLE user_roles_legacy")
    
    # 2. Rename old user_roles to user_roles_legacy
    print("Renaming user_roles -> user_roles_legacy...")
    cursor.execute("ALTER TABLE user_roles RENAME TO user_roles_legacy")
    
    # 3. Create new user_roles as association table
    print("Creating new user_roles association table...")
    cursor.execute("""
        CREATE TABLE user_roles (
            user_id INTEGER NOT NULL,
            role_id INTEGER NOT NULL,
            assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            assigned_by INTEGER,
            PRIMARY KEY (user_id, role_id),
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
            FOREIGN KEY (assigned_by) REFERENCES users(id)
        )
    """)
    
    conn.commit()
    print("Done! user_roles table fixed.")
    
    # Verify
    cursor.execute("PRAGMA table_info(user_roles)")
    print("New user_roles structure:", cursor.fetchall())
    
except Exception as e:
    conn.rollback()
    print(f"Error: {e}")
finally:
    conn.close()

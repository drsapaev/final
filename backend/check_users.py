"""Check and fix registrar users"""
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Check existing users with Receptionist role
print("=== Users with Receptionist role ===")
cursor.execute("SELECT id, username, email, role, is_active FROM users WHERE role = 'Receptionist'")
for row in cursor.fetchall():
    print(row)

print("\n=== All users ===")
cursor.execute("SELECT id, username, email, role, is_active FROM users ORDER BY role, username")
for row in cursor.fetchall():
    print(row)

conn.close()

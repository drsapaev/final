import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Проверяем пользователя admin
cursor.execute("SELECT id, username, password_hash, role FROM users WHERE username='admin'")
user = cursor.fetchone()
if user:
    print(f"User found: ID={user[0]}, Username={user[1]}, Password Hash={user[2][:20]}..., Role={user[3]}")
else:
    print("User not found")

conn.close()


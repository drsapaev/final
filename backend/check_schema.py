import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

# Проверяем структуру таблицы users
cursor.execute("PRAGMA table_info(users)")
columns = cursor.fetchall()
print("Users table columns:")
for col in columns:
    print(f"  {col[1]} ({col[2]})")

# Проверяем пользователя admin
cursor.execute("SELECT * FROM users WHERE username='admin'")
user = cursor.fetchone()
if user:
    print(f"\nUser found: {user}")
else:
    print("\nUser not found")

conn.close()


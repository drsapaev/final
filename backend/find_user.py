#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

print("🔍 Ищу пользователя admin@example.com:")
cursor.execute('SELECT id, username, email FROM users WHERE username = "admin@example.com"')
row = cursor.fetchone()
if row:
    print(f"  ID: {row[0]}")
    print(f"  Username: {row[1]}")
    print(f"  Email: {row[2]}")
else:
    print("  ❌ Пользователь не найден")

    print("🔍 Все пользователи:")
    cursor.execute('SELECT id, username, email FROM users LIMIT 10')
    users = cursor.fetchall()
    for user in users:
        print(f"  {user[0]}: {user[1]} ({user[2]})")

conn.close()

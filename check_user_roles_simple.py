#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

print("📋 Содержимое таблицы user_roles:")
cursor.execute('SELECT * FROM user_roles WHERE user_id = 19')
rows = cursor.fetchall()
if rows:
    print("  Найденные записи:")
    for row in rows:
        print(f"    user_id: {row[0]}, role_id: {row[1]}")

    # Проверим роль
    for row in rows:
        cursor.execute('SELECT name FROM roles WHERE id = ?', (row[1],))
        role = cursor.fetchone()
        print(f"    Роль: {role[0] if role else 'Unknown'}")
else:
    print("  ❌ Нет записей для user_id = 19")

print("\n📋 Все роли в системе:")
cursor.execute('SELECT id, name, description FROM roles')
roles = cursor.fetchall()
for role in roles:
    print(f"  {role[0]}: {role[1]} - {role[2]}")

conn.close()

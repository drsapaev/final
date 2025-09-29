#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()

print("🔍 Ищу таблицы связанные с user и role:")
cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%user%role%'")
tables = cursor.fetchall()
for table in tables:
    print(f"  - {table[0]}")

    # Проверим структуру
    cursor.execute(f"PRAGMA table_info({table[0]})")
    columns = cursor.fetchall()
    print("    Колонки:")
    for col in columns:
        print(f"      {col[1]}: {col[2]}")

conn.close()

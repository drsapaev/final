#!/usr/bin/env python3
import sqlite3

conn = sqlite3.connect('clinic.db')
cursor = conn.cursor()
cursor.execute('SELECT name FROM sqlite_master WHERE type="table"')
tables = [row[0] for row in cursor.fetchall()]
print("Таблицы в базе данных:")
for table in tables:
    print(f"  - {table}")
conn.close()

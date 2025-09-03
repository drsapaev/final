# app/scripts/add_planned_date.py

import os
import sqlite3

DB_PATH = "clinic.db"

if not os.path.exists(DB_PATH):
    print("❌ База данных clinic.db не найдена")
    exit(1)

db = sqlite3.connect(DB_PATH)
cur = db.cursor()

# Получаем все колонки таблицы visits
cur.execute("PRAGMA table_info(visits);")
columns = [col[1] for col in cur.fetchall()]

if "planned_date" in columns:
    print("ℹ️ Колонка planned_date уже существует")
else:
    cur.execute("ALTER TABLE visits ADD COLUMN planned_date DATE;")
    cur.execute(
        "UPDATE visits SET planned_date = DATE('now') WHERE planned_date IS NULL;"
    )
    print("✅ Колонка planned_date успешно добавлена и заполнена")

db.commit()
db.close()

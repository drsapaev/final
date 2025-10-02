#!/usr/bin/env python3
"""
Проверка структуры базы данных
"""

import sqlite3
import os

def check_database_structure():
    """Проверяем структуру базы данных"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Получаем список всех таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        print("📋 Таблицы в базе данных:")
        for table in tables:
            print(f"  - {table[0]}")

        # Проверяем, есть ли таблица с записями
        if any('appointment' in table[0].lower() for table in tables):
            print("\n🔍 Ищем таблицу с записями...")
            for table in tables:
                if 'appointment' in table[0].lower():
                    print(f"\n📊 Таблица: {table[0]}")
                    cursor.execute(f"SELECT COUNT(*) FROM {table[0]}")
                    count = cursor.fetchone()[0]
                    print(f"Количество записей: {count}")
                    
                    if count > 0:
                        cursor.execute(f"SELECT * FROM {table[0]} LIMIT 1")
                        sample = cursor.fetchone()
                        print(f"Пример записи: {sample}")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    check_database_structure()

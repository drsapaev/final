#!/usr/bin/env python3
"""
Проверка лабораторных услуг в базе данных
"""

import sqlite3
import os

def check_lab_services():
    """Проверяем лабораторные услуги"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        # Подсчитываем лабораторные услуги
        cursor.execute('SELECT COUNT(*) FROM services WHERE category_code = "L" AND active = 1')
        count = cursor.fetchone()[0]
        print(f"📊 Лабораторных услуг в базе данных: {count}")

        # Получаем список лабораторных услуг
        cursor.execute('SELECT service_code, name FROM services WHERE category_code = "L" AND active = 1 ORDER BY service_code')
        services = cursor.fetchall()

        print("\n📋 Лабораторные услуги:")
        for code, name in services:
            print(f"   {code} - {name}")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    check_lab_services()

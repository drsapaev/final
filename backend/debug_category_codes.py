#!/usr/bin/env python3
"""
Отладка кодов категорий в базе данных
"""

import sqlite3
import os

def debug_category_codes():
    """Проверяем коды категорий в базе данных"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔍 Проверяем коды категорий в базе данных...")

        # Получаем все услуги с их кодами
        cursor.execute("""
            SELECT service_code, name, category_code, code FROM services
            WHERE category_code IN ('D', 'D_PROC', 'P', 'C', 'K', 'S', 'L', 'ECG')
            ORDER BY category_code, service_code
        """)

        services = cursor.fetchall()
        print("\n📋 Услуги по категориям в базе данных:")
        for service_code, name, category_code, code in services:
            print(f"   {service_code} - {name} (category_code: {category_code}, code: {code})")

        # Проверим дерматологические процедуры отдельно
        print("\n🔍 Дерматологические процедуры:")
        cursor.execute("""
            SELECT service_code, name, category_code FROM services
            WHERE service_code LIKE 'D_PROC%'
        """)

        derm_proc = cursor.fetchall()
        for service_code, name, category_code in derm_proc:
            print(f"   {service_code} - {name} (category_code: {category_code})")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    debug_category_codes()

#!/usr/bin/env python3
"""
Исправление распределения дерматологических услуг
Согласно требованиям: Дерматолог - только консультация, остальные в Процедуры
"""

import sqlite3
import os

def fix_dermatology_distribution():
    """Исправляем распределение дерматологических услуг"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔄 Исправляем распределение дерматологических услуг...")

        # Исправляем category_code для дерматологических процедур
        # D_PROC01, D_PROC02, D_PROC03 должны иметь category_code = 'D_PROC', а не 'D'
        cursor.execute("""
            UPDATE services
            SET category_code = 'D_PROC'
            WHERE service_code IN ('D_PROC01', 'D_PROC02', 'D_PROC03')
            AND category_code = 'D'
        """)

        if cursor.rowcount > 0:
            print(f"✅ Исправлены category_code для {cursor.rowcount} дерматологических процедур")

        # Проверяем текущее распределение
        cursor.execute("""
            SELECT service_code, name, category_code FROM services
            WHERE category_code IN ('D', 'D_PROC')
            ORDER BY category_code, service_code
        """)

        services = cursor.fetchall()
        print("\n📋 Текущее распределение дерматологических услуг:")
        for service_code, name, category_code in services:
            category_name = {
                'D': 'Дерматолог',
                'D_PROC': 'Процедуры (дерматологические)'
            }.get(category_code, category_code)
            print(f"   {service_code} - {name} ({category_name})")

        conn.commit()
        print("✅ Исправление распределения завершено")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    fix_dermatology_distribution()

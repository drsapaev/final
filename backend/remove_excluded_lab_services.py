#!/usr/bin/env python3
"""
Удаление исключенных лабораторных услуг (L02, L31, L50)
"""

import sqlite3
import os

def remove_excluded_lab_services():
    """Удаляем исключенные лабораторные услуги"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔄 Удаляем исключенные лабораторные услуги...")

        # Исключаемые услуги
        excluded_services = ['L02', 'L31', 'L50']

        for service_code in excluded_services:
            cursor.execute('DELETE FROM services WHERE service_code = ?', (service_code,))
            if cursor.rowcount > 0:
                print(f"✅ Удалена лабораторная услуга: {service_code}")
            else:
                print(f"⚠️ Услуга не найдена: {service_code}")

        conn.commit()
        print("✅ Удаление исключенных услуг завершено")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    remove_excluded_lab_services()

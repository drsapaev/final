#!/usr/bin/env python3
"""
Добавление отсутствующей услуги HCV Экспресс тест
"""

import sqlite3
import os

def add_missing_hcv_service():
    """Добавляем отсутствующую услугу HCV Экспресс тест"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔄 Добавляем HCV Экспресс тест...")

        # Проверяем, существует ли услуга
        cursor.execute('SELECT id FROM services WHERE name = "HCV Экспресс тест"')
        existing = cursor.fetchone()

        if existing:
            print("✅ HCV Экспресс тест уже существует")
        else:
            # Добавляем услугу
            cursor.execute("""
                INSERT INTO services (code, name, department, unit, price, currency, active, category_code, service_code, duration_minutes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, ('lab.hcv', 'HCV Экспресс тест', 'laboratory', 'анализ', 12000.00, 'UZS', 1, 'L', 'L31', 5))
            print("✅ Добавлен HCV Экспресс тест (L31)")

        conn.commit()
        print("✅ Добавление завершено")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    add_missing_hcv_service()

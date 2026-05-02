#!/usr/bin/env python3
"""
Создание таблиц services и service_categories вручную
"""

import sqlite3
import os

def create_services_tables():
    """Создаем таблицы вручную"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔄 Создаем таблицы services и service_categories...")

        # Создаем таблицу service_categories
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS service_categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(50) NOT NULL UNIQUE,
                name_ru VARCHAR(100),
                name_uz VARCHAR(100),
                name_en VARCHAR(100),
                specialty VARCHAR(100),
                active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Создаем таблицу services
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS services (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                code VARCHAR(32),
                name VARCHAR(256) NOT NULL,
                department VARCHAR(64),
                unit VARCHAR(32),
                price DECIMAL(12, 2),
                currency VARCHAR(8) DEFAULT 'UZS',
                active BOOLEAN DEFAULT 1,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,

                -- Новые поля для классификации
                category_code VARCHAR(1),
                service_code VARCHAR(10) UNIQUE,
                category_id INTEGER,
                duration_minutes INTEGER DEFAULT 30,
                doctor_id INTEGER,

                -- Поля для мастера регистрации
                requires_doctor BOOLEAN DEFAULT 0,
                queue_tag VARCHAR(32),
                is_consultation BOOLEAN DEFAULT 0,
                allow_doctor_price_override BOOLEAN DEFAULT 0,

                FOREIGN KEY (category_id) REFERENCES service_categories(id),
                FOREIGN KEY (doctor_id) REFERENCES doctors(id)
            )
        """)

        # Создаем индексы
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_services_category_code ON services(category_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_services_service_code ON services(service_code)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_services_requires_doctor ON services(requires_doctor)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_services_queue_tag ON services(queue_tag)")
        cursor.execute("CREATE INDEX IF NOT EXISTS ix_services_is_consultation ON services(is_consultation)")

        conn.commit()
        print("✅ Таблицы созданы успешно")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    create_services_tables()

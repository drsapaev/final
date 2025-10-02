#!/usr/bin/env python3
"""
Проверка таблиц в базе данных
"""

import sqlite3
import os

def check_database_tables():
    """Проверяем таблицы в базе данных"""

    db_path = 'clinic.db'

    if not os.path.exists(db_path):
        print(f"❌ База данных '{db_path}' не найдена.")
        return False

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    try:
        print("🔍 Проверяем таблицы в базе данных...")

        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()

        print(f"\n📊 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"   • {table[0]}")

        # Проверим структуру таблицы services или service_catalog, если она существует
        service_table = None
        for table in tables:
            if table[0] in ['services', 'service_catalog']:
                service_table = table[0]
                break

        if service_table:
            print(f"\n📋 Структура таблицы {service_table}:")
            cursor.execute(f"PRAGMA table_info({service_table})")
            columns = cursor.fetchall()
            for col in columns:
                print(f"   {col[1]} ({col[2]}) - {'NOT NULL' if col[3] else 'NULL'}")

            # Посчитаем количество услуг
            cursor.execute(f"SELECT COUNT(*) FROM {service_table} WHERE active = 1")
            count = cursor.fetchone()[0]
            print(f"\n📊 Активных услуг в базе: {count}")

            # Покажем примеры услуг
            cursor.execute(f"SELECT service_code, name, category_code FROM {service_table} WHERE active = 1 LIMIT 5")
            services = cursor.fetchall()
            print("\n📋 Примеры услуг:")
            for service_code, name, category_code in services:
                print(f"   {service_code} - {name} (категория: {category_code})")
        else:
            print("\n❌ Таблица услуг не найдена!")
            print("Доступные таблицы:")
            for table in tables:
                print(f"   • {table[0]}")
            print("Необходимо запустить миграции или скрипт инициализации.")

        return True

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    check_database_tables()

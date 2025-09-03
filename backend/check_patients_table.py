#!/usr/bin/env python3
"""
Скрипт для проверки структуры таблицы patients
"""
import sqlite3


def check_patients_table():
    """Проверяем структуру таблицы patients"""
    try:
        # Подключаемся к базе данных
        conn = sqlite3.connect("clinic.db")
        cursor = conn.cursor()

        print("🔍 Проверяем структуру таблицы patients...")

        # Получаем информацию о таблице
        cursor.execute("PRAGMA table_info(patients)")
        columns = cursor.fetchall()

        if not columns:
            print("❌ Таблица patients не существует!")
            return

        print("✅ Таблица patients найдена. Колонки:")
        print("-" * 50)

        for col in columns:
            col_id, name, type_name, not_null, default_val, pk = col
            nullable = "NOT NULL" if not_null else "NULL"
            primary = "PRIMARY KEY" if pk else ""
            print(f"  {name:<15} {type_name:<15} {nullable:<8} {primary}")

        print("-" * 50)

        # Проверяем количество записей
        cursor.execute("SELECT COUNT(*) FROM patients")
        count = cursor.fetchone()[0]
        print(f"📊 Количество записей: {count}")

        # Показываем несколько примеров
        if count > 0:
            cursor.execute("SELECT * FROM patients LIMIT 3")
            rows = cursor.fetchall()
            print("\n📋 Примеры записей:")
            for i, row in enumerate(rows, 1):
                print(f"  Запись {i}: {row}")

        conn.close()

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    check_patients_table()

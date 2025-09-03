#!/usr/bin/env python3
"""
Скрипт для проверки существующих таблиц в базе данных
"""
import os
import sqlite3


def check_tables():
    """Проверяем существующие таблицы"""
    db_path = "clinic.db"

    if not os.path.exists(db_path):
        print(f"❌ База данных {db_path} не найдена")
        return

    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Получаем список всех таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()

        print(f"📋 Таблицы в базе данных {db_path}:")
        for table in tables:
            print(f"  - {table[0]}")

        # Проверяем конкретно таблицы вебхуков
        payment_tables = [t[0] for t in tables if "payment" in t[0].lower()]
        if payment_tables:
            print(f"\n💰 Таблицы вебхуков оплат:")
            for table in payment_tables:
                print(f"  - {table}")
        else:
            print(f"\n💰 Таблицы вебхуков оплат не найдены")

        conn.close()

    except Exception as e:
        print(f"❌ Ошибка при проверке таблиц: {e}")


if __name__ == "__main__":
    check_tables()

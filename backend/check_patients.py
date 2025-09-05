#!/usr/bin/env python3
"""
Скрипт для проверки структуры таблицы patients
"""

import sqlite3


def check_patients_table():
    """Проверка структуры таблицы patients"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()

    try:
        cursor.execute("PRAGMA table_info(patients)")
        columns = cursor.fetchall()
        print("Структура таблицы patients:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    check_patients_table()

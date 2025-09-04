#!/usr/bin/env python3
"""
Скрипт для проверки структуры базы данных
"""

import sqlite3

def check_database():
    """Проверка структуры базы данных"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    try:
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        print("Таблицы в базе данных:")
        for table in tables:
            print(f"  - {table}")
        
        # Проверяем структуру таблицы users
        if 'users' in tables:
            print("\nСтруктура таблицы users:")
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
        
        # Проверяем структуру таблицы patients
        if 'patients' in tables:
            print("\nСтруктура таблицы patients:")
            cursor.execute("PRAGMA table_info(patients)")
            columns = cursor.fetchall()
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
        
        # Проверяем пользователей
        if 'users' in tables:
            print("\nПользователи в системе:")
            cursor.execute("SELECT username, role, is_active FROM users")
            users = cursor.fetchall()
            for user in users:
                print(f"  {user[0]} - {user[1]} (активен: {user[2]})")
                
    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_database()

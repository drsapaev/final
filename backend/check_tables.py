#!/usr/bin/env python3
"""
Проверить таблицы в базе данных
"""
import sqlite3

def check_tables():
    """Проверить какие таблицы есть в БД"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print("📋 Таблицы в базе данных:")
        if tables:
            for table in tables:
                print(f"  ✅ {table[0]}")
        else:
            print("  ❌ Таблицы не найдены")
        
        # Проверим есть ли таблица users
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
        users_table = cursor.fetchone()
        
        if users_table:
            print(f"\n✅ Таблица 'users' существует")
            # Проверим структуру таблицы users
            cursor.execute("PRAGMA table_info(users)")
            columns = cursor.fetchall()
            print("   Структура таблицы users:")
            for col in columns:
                print(f"     - {col[1]} ({col[2]})")
        else:
            print(f"\n❌ Таблица 'users' НЕ существует")
            
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_tables()
#!/usr/bin/env python3
"""
Быстрая проверка базы данных
"""

import sqlite3
import os

def check_database():
    """Проверка состояния базы данных"""
    
    db_path = "clinic.db"
    
    print(f"🔍 Проверка базы данных: {db_path}")
    print("-" * 50)
    
    if not os.path.exists(db_path):
        print("❌ База данных не найдена!")
        return False
    
    print(f"✅ Файл базы данных существует (размер: {os.path.getsize(db_path)} байт)")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Получаем список таблиц
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"📋 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"  - {table[0]}")
        
        # Проверяем таблицу users
        if ('users',) in tables:
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            print(f"👥 Пользователей в базе: {user_count}")
            
            # Показываем первых 3 пользователей
            cursor.execute("SELECT id, username, role FROM users LIMIT 3")
            users = cursor.fetchall()
            print("📝 Примеры пользователей:")
            for user in users:
                print(f"  - ID: {user[0]}, Username: {user[1]}, Role: {user[2]}")
        else:
            print("❌ Таблица users не найдена!")
        
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Ошибка при работе с БД: {e}")
        return False

if __name__ == "__main__":
    check_database()

#!/usr/bin/env python3
"""
Проверка базы данных
"""
import sqlite3
import os

def check_database():
    """Проверка базы данных"""
    print("🔍 ПРОВЕРКА БАЗЫ ДАННЫХ")
    print("=" * 40)
    
    db_path = "clinic.db"
    
    if not os.path.exists(db_path):
        print(f"❌ База данных {db_path} не найдена!")
        return
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Проверяем таблицы
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = cursor.fetchall()
        
        print(f"📋 Найдено таблиц: {len(tables)}")
        for table in tables:
            print(f"   - {table[0]}")
        
        # Проверяем таблицу users
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        print(f"👥 Пользователей в базе: {user_count}")
        
        # Проверяем admin пользователя
        cursor.execute("SELECT username, role FROM users WHERE username='admin'")
        admin = cursor.fetchone()
        if admin:
            print(f"👤 Admin пользователь: {admin[0]} (роль: {admin[1]})")
        else:
            print("❌ Admin пользователь не найден!")
        
        # Проверяем таблицу telegram_configs
        cursor.execute("SELECT COUNT(*) FROM telegram_configs")
        telegram_count = cursor.fetchone()[0]
        print(f"📱 Telegram конфигураций: {telegram_count}")
        
        conn.close()
        print("✅ Проверка завершена")
        
    except Exception as e:
        print(f"❌ Ошибка проверки: {e}")

if __name__ == "__main__":
    check_database()
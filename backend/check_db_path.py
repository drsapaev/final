#!/usr/bin/env python3
"""
Проверка пути к базе данных
"""
import sqlite3
import os

def check_database_path():
    """Проверка пути к базе данных"""
    print("🔍 ПРОВЕРКА ПУТИ К БАЗЕ ДАННЫХ")
    print("=" * 40)
    
    # Текущая директория
    current_dir = os.getcwd()
    print(f"📁 Текущая директория: {current_dir}")
    
    # Ищем .db файлы
    db_files = [f for f in os.listdir('.') if f.endswith('.db')]
    print(f"📋 Найдено .db файлов: {len(db_files)}")
    for db_file in db_files:
        print(f"   - {db_file}")
    
    # Проверяем clinic.db
    if 'clinic.db' in db_files:
        print("\n✅ clinic.db найден")
        try:
            conn = sqlite3.connect('clinic.db')
            cursor = conn.cursor()
            
            # Проверяем таблицу users
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            users_exists = bool(cursor.fetchone())
            print(f"👥 Таблица users существует: {users_exists}")
            
            if users_exists:
                cursor.execute("SELECT COUNT(*) FROM users")
                user_count = cursor.fetchone()[0]
                print(f"👤 Количество пользователей: {user_count}")
            
            conn.close()
        except Exception as e:
            print(f"❌ Ошибка проверки clinic.db: {e}")
    else:
        print("❌ clinic.db не найден")
    
    # Проверяем data.db
    if 'data.db' in db_files:
        print("\n⚠️ data.db найден (возможно старая база)")
        try:
            conn = sqlite3.connect('data.db')
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
            users_exists = bool(cursor.fetchone())
            print(f"👥 Таблица users в data.db: {users_exists}")
            conn.close()
        except Exception as e:
            print(f"❌ Ошибка проверки data.db: {e}")

if __name__ == "__main__":
    check_database_path()

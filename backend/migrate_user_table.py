#!/usr/bin/env python3
"""
Миграция таблицы users для добавления полей created_at и updated_at
"""
import sqlite3
import sys
import os

# Добавляем путь к приложению
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def migrate_user_table():
    """Добавляет поля created_at и updated_at в таблицу users"""
    print("🔧 МИГРАЦИЯ ТАБЛИЦЫ USERS")
    print("=" * 40)
    
    try:
        conn = sqlite3.connect('clinic.db')
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже поля created_at и updated_at
        cursor.execute("PRAGMA table_info(users)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'created_at' in columns and 'updated_at' in columns:
            print("✅ Поля created_at и updated_at уже существуют")
            conn.close()
            return True
        
        print("📋 Добавление полей created_at и updated_at...")
        
        # Добавляем поле created_at
        if 'created_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN created_at DATETIME")
            print("✅ Поле created_at добавлено")
        
        # Добавляем поле updated_at
        if 'updated_at' not in columns:
            cursor.execute("ALTER TABLE users ADD COLUMN updated_at DATETIME")
            print("✅ Поле updated_at добавлено")
        
        # Обновляем существующие записи, устанавливая created_at на текущее время
        cursor.execute("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
        cursor.execute("UPDATE users SET updated_at = CURRENT_TIMESTAMP WHERE updated_at IS NULL")
        
        conn.commit()
        conn.close()
        
        print("✅ Миграция завершена успешно")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False

if __name__ == "__main__":
    success = migrate_user_table()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""
Проверка структуры базы данных
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.session import SessionLocal
from sqlalchemy import text

def check_db_structure():
    """Проверить структуру БД"""
    db = SessionLocal()
    try:
        # Проверяем структуру таблицы users
        result = db.execute(text("PRAGMA table_info(users);"))
        columns = result.fetchall()
        
        print("📊 Структура таблицы 'users':")
        for column in columns:
            print(f"  - {column[1]} ({column[2]}) - NOT NULL: {column[3]}, DEFAULT: {column[4]}")
            
        # Проверяем, есть ли данные в таблице
        result = db.execute(text("SELECT COUNT(*) FROM users;"))
        count = result.fetchone()[0]
        print(f"\n📈 Количество записей в таблице users: {count}")
        
        if count > 0:
            # Показываем первые несколько записей
            result = db.execute(text("SELECT id, username, email, role FROM users LIMIT 5;"))
            users = result.fetchall()
            print("\n👥 Первые пользователи:")
            for user in users:
                print(f"  - ID: {user[0]}, Username: {user[1]}, Email: {user[2]}, Role: {user[3]}")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке структуры БД: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 Проверка структуры базы данных...")
    check_db_structure()


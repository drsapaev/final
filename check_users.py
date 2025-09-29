#!/usr/bin/env python3
"""
Проверка пользователей в базе данных
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))

from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy import text

def check_users():
    """Проверить пользователей в БД"""
    db = SessionLocal()
    try:
        # Проверяем, есть ли таблица users
        result = db.execute(text("SELECT name FROM sqlite_master WHERE type='table' AND name='users';"))
        table_exists = result.fetchone()
        
        if not table_exists:
            print("❌ Таблица 'users' не существует!")
            return
            
        print("✅ Таблица 'users' существует")
        
        # Получаем всех пользователей
        users = db.query(User).all()
        print(f"📊 Всего пользователей в БД: {len(users)}")
        
        if users:
            print("\n👥 Список пользователей:")
            for user in users:
                print(f"  - ID: {user.id}, Email: {user.email}, Role: {user.role}, Active: {user.is_active}")
                
            # Ищем admin пользователя
            admin = db.query(User).filter(User.email == "admin@example.com").first()
            if admin:
                print(f"\n✅ Пользователь admin найден:")
                print(f"  - ID: {admin.id}")
                print(f"  - Email: {admin.email}")
                print(f"  - Role: {admin.role}")
                print(f"  - Active: {admin.is_active}")
                print(f"  - Password hash: {admin.password_hash[:20]}...")
            else:
                print("\n❌ Пользователь admin@example.com не найден!")
        else:
            print("❌ Пользователи не найдены в БД!")
            
    except Exception as e:
        print(f"❌ Ошибка при проверке пользователей: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    print("🔍 Проверка пользователей в базе данных...")
    check_users()


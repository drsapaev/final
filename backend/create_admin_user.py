#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.db.session import SessionLocal
from app.models.user import User
from app.core.security import get_password_hash

def create_admin_user():
    """Создает пользователя admin с паролем admin"""
    db = SessionLocal()
    try:
        # Проверяем, существует ли уже пользователь admin
        existing_user = db.query(User).filter(User.username == "admin").first()
        if existing_user:
            print("✅ Пользователь admin уже существует")
            return
        
        # Создаем нового пользователя admin
        admin_user = User()
        admin_user.username = "admin"
        admin_user.email = "admin@clinic.local"
        admin_user.full_name = "Администратор"
        admin_user.hashed_password = get_password_hash("admin")
        admin_user.is_active = True
        admin_user.is_superuser = True
        admin_user.role = "Admin"
        
        db.add(admin_user)
        db.commit()
        print("✅ Пользователь admin создан успешно")
        print("   Логин: admin")
        print("   Пароль: admin")
        
    except Exception as e:
        print(f"❌ Ошибка создания пользователя: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    create_admin_user()

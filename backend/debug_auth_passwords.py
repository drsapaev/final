#!/usr/bin/env python3
"""
Диагностика паролей пользователей
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base_class import Base
from app.models.user import User
from app.core.security import verify_password

os.environ["DATABASE_URL"] = "sqlite:///./clinic.db"
os.environ["PYTHONPATH"] = "C:\\final\\backend"

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clinic.db")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def debug_passwords():
    db = SessionLocal()
    try:
        print("🔍 ДИАГНОСТИКА ПАРОЛЕЙ ПОЛЬЗОВАТЕЛЕЙ")
        print("===================================")
        
        # Тестовые пароли
        test_passwords = {
            "admin": "admin123",
            "registrar": "registrar123", 
            "lab": "lab123",
            "doctor": "doctor123",
            "cashier": "cashier123",
            "cardio": "cardio123",
            "derma": "derma123",
            "dentist": "dentist123"
        }
        
        for username, password in test_passwords.items():
            user = db.query(User).filter(User.username == username).first()
            if user:
                print(f"\n👤 Пользователь: {username}")
                print(f"   ID: {user.id}")
                print(f"   Email: {user.email}")
                print(f"   Роль: {user.role}")
                print(f"   Активен: {user.is_active}")
                print(f"   Хеш пароля: {user.hashed_password[:50]}...")
                
                # Проверяем пароль
                is_valid = verify_password(password, user.hashed_password)
                print(f"   Пароль '{password}': {'✅ ВЕРНЫЙ' if is_valid else '❌ НЕВЕРНЫЙ'}")
                
                if not is_valid:
                    print(f"   ⚠️ Проблема с паролем для {username}!")
            else:
                print(f"\n❌ Пользователь {username} не найден!")
        
        print(f"\n📊 ИТОГИ ДИАГНОСТИКИ:")
        print(f"   Проверено пользователей: {len(test_passwords)}")
        
    except Exception as e:
        print(f"❌ Ошибка при диагностике: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    debug_passwords()

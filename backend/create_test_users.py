#!/usr/bin/env python3
"""
Создание тестовых пользователей для всех ролей
"""
import os
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base_class import Base
from app.models.user import User
from app.core.security import get_password_hash

os.environ["DATABASE_URL"] = "sqlite:///./clinic.db"
os.environ["PYTHONPATH"] = "C:\\final\\backend"

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./clinic.db")
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_test_users():
    db = SessionLocal()
    try:
        print("🔧 СОЗДАНИЕ ТЕСТОВЫХ ПОЛЬЗОВАТЕЛЕЙ")
        print("=================================")
        
        # Список пользователей для создания
        test_users = [
            {
                "username": "registrar",
                "email": "registrar@clinic.com",
                "full_name": "Регистратор Иванов",
                "role": "registrar",
                "password": "registrar123"
            },
            {
                "username": "lab",
                "email": "lab@clinic.com", 
                "full_name": "Лаборант Петров",
                "role": "lab",
                "password": "lab123"
            },
            {
                "username": "doctor",
                "email": "doctor@clinic.com",
                "full_name": "Доктор Сидоров",
                "role": "doctor", 
                "password": "doctor123"
            },
            {
                "username": "cashier",
                "email": "cashier@clinic.com",
                "full_name": "Кассир Козлов",
                "role": "cashier",
                "password": "cashier123"
            },
            {
                "username": "cardio",
                "email": "cardio@clinic.com",
                "full_name": "Кардиолог Волков",
                "role": "cardio",
                "password": "cardio123"
            },
            {
                "username": "derma",
                "email": "derma@clinic.com",
                "full_name": "Дерматолог Морозов",
                "role": "derma",
                "password": "derma123"
            },
            {
                "username": "dentist",
                "email": "dentist@clinic.com",
                "full_name": "Стоматолог Лебедев",
                "role": "dentist",
                "password": "dentist123"
            }
        ]
        
        created_count = 0
        updated_count = 0
        
        for user_data in test_users:
            # Проверяем, существует ли пользователь
            existing_user = db.query(User).filter(User.username == user_data["username"]).first()
            
            if existing_user:
                print(f"   ℹ️ Пользователь {user_data['username']} уже существует")
                # Обновляем пароль
                existing_user.hashed_password = get_password_hash(user_data["password"])
                existing_user.is_active = True
                db.commit()
                updated_count += 1
            else:
                print(f"   ➕ Создаем пользователя {user_data['username']}...")
                new_user = User(
                    username=user_data["username"],
                    email=user_data["email"],
                    full_name=user_data["full_name"],
                    hashed_password=get_password_hash(user_data["password"]),
                    role=user_data["role"],
                    is_active=True,
                    is_superuser=False,
                    created_at=datetime.utcnow(),
                    updated_at=datetime.utcnow()
                )
                db.add(new_user)
                db.commit()
                db.refresh(new_user)
                created_count += 1
                print(f"   ✅ Пользователь {user_data['username']} создан с ID: {new_user.id}")
        
        print(f"\n📊 ИТОГИ:")
        print(f"   ➕ Создано новых пользователей: {created_count}")
        print(f"   🔄 Обновлено существующих: {updated_count}")
        print(f"   📝 Всего обработано: {created_count + updated_count}")
        
        # Проверяем всех пользователей
        print(f"\n👥 СПИСОК ВСЕХ ПОЛЬЗОВАТЕЛЕЙ:")
        all_users = db.query(User).all()
        for user in all_users:
            print(f"   - {user.username} ({user.role}) - {'✅' if user.is_active else '❌'}")
        
        print(f"\n🎉 Создание тестовых пользователей завершено успешно!")
        
    except Exception as e:
        db.rollback()
        print(f"❌ Ошибка при создании пользователей: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    create_test_users()

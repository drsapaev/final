#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных
Создает все необходимые таблицы и добавляет базовых пользователей
"""

import os
import sys
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from app.db.base import Base
from app.models.user import User
from app.models.user_profile import UserRole, UserPermission, RolePermission, UserGroup, UserGroupMember
from app.models.authentication import RefreshToken, UserActivity, SecurityEvent, LoginAttempt
from app.core.config import settings
from passlib.context import CryptContext

# Создаем движок базы данных
engine = create_engine(settings.DATABASE_URL, echo=True)

# Создаем все таблицы
print("🗄️ Создание таблиц в базе данных...")
Base.metadata.create_all(bind=engine)

# Создаем контекст для хеширования паролей
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

# Создаем базовых пользователей
print("👥 Создание базовых пользователей...")

from sqlalchemy.orm import sessionmaker
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

db = SessionLocal()

try:
    # Проверяем, есть ли уже пользователи
    existing_users = db.query(User).count()
    if existing_users > 0:
        print(f"✅ В базе уже есть {existing_users} пользователей")
    else:
        # Создаем роли
        admin_role = UserRole(
            name="Admin",
            description="Администратор системы",
            permissions=["all"]
        )
        doctor_role = UserRole(
            name="Doctor", 
            description="Врач",
            permissions=["read_patients", "write_emr", "read_appointments"]
        )
        registrar_role = UserRole(
            name="Registrar",
            description="Регистратор",
            permissions=["read_patients", "write_appointments", "read_queues"]
        )
        
        db.add_all([admin_role, doctor_role, registrar_role])
        db.flush()  # Получаем ID ролей
        
        # Создаем пользователей
        users = [
            User(
                username="admin",
                email="admin@clinic.local",
                full_name="Администратор",
                hashed_password=get_password_hash("admin123"),
                role="Admin",
                is_active=True,
                is_superuser=True
            ),
            User(
                username="doctor",
                email="doctor@clinic.local", 
                full_name="Доктор Иванов",
                hashed_password=get_password_hash("doctor123"),
                role="Doctor",
                is_active=True,
                is_superuser=False
            ),
            User(
                username="registrar",
                email="registrar@clinic.local",
                full_name="Регистратор Петрова", 
                hashed_password=get_password_hash("registrar123"),
                role="Registrar",
                is_active=True,
                is_superuser=False
            )
        ]
        
        db.add_all(users)
        db.commit()
        
        print("✅ Созданы пользователи:")
        print("  - admin / admin123 (Администратор)")
        print("  - doctor / doctor123 (Врач)")
        print("  - registrar / registrar123 (Регистратор)")
        
except Exception as e:
    print(f"❌ Ошибка при создании пользователей: {e}")
    db.rollback()
finally:
    db.close()

print("🎉 Инициализация базы данных завершена!")

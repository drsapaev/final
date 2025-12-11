#!/usr/bin/env python3
"""
Скрипт для инициализации базы данных
Создает все необходимые таблицы и добавляет базовых пользователей
"""

import os
import sys
from pathlib import Path
from datetime import time

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from sqlalchemy import create_engine
from app.db.base import Base
from app.models.user import User
from app.models.role_permission import Role, Permission, UserGroup
from app.models.authentication import RefreshToken, UserActivity, SecurityEvent, LoginAttempt
from app.models.department import Department
from app.models.clinic import Doctor
from app.core.config import settings
from passlib.context import CryptContext

# Создаем движок базы данных
engine = create_engine(settings.DATABASE_URL, echo=True)

# Создаем все таблицы
print("🗄️ Создание таблиц в базе данных...")
Base.metadata.create_all(bind=engine)

# Создаем контекст для хеширования паролей
# Используем argon2, так как он установлен и сконфигурирован в security.py
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")

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
        admin_role = Role(
            name="Admin",
            display_name="Администратор",
            description="Администратор системы"
        )
        doctor_role = Role(
            name="Doctor",
            display_name="Врач",
            description="Врач"
        )
        registrar_role = Role(
            name="Registrar",
            display_name="Регистратор",
            description="Регистратор"
        )

        db.add_all([admin_role, doctor_role, registrar_role])
        db.flush()  # Получаем ID ролей

        # Создаем пользователей
        admin_user = User(
            username="admin",
            email="admin@clinic.local",
            full_name="Администратор",
            hashed_password=get_password_hash("admin123"),
            role="Admin",
            is_active=True,
            is_superuser=True
        )

        doctor_user = User(
            username="doctor",
            email="doctor@clinic.local",
            full_name="Доктор Иванов",
            hashed_password=get_password_hash("doctor123"),
            role="Doctor",
            is_active=True,
            is_superuser=False
        )

        registrar_user = User(
            username="registrar",
            email="registrar@clinic.local",
            full_name="Регистратор Петрова",
            hashed_password=get_password_hash("registrar123"),
            role="Registrar",
            is_active=True,
            is_superuser=False
        )

        users = [admin_user, doctor_user, registrar_user]

        db.add_all(users)
        db.flush() # Получаем ID пользователей

        # Создаем отдел
        general_dept = Department(
            key="general",
            name_ru="Общее отделение",
            active=True
        )
        db.add(general_dept)
        db.flush()

        # Создаем доктора
        doctor = Doctor(
            user_id=doctor_user.id,
            department_id=general_dept.id,
            specialty="General",
            active=True,
            start_number_online=1,
            max_online_per_day=20,
            auto_close_time=time(9, 0)
        )
        db.add(doctor)

        db.commit()

        print("✅ Созданы пользователи:")
        print("  - admin / admin123 (Администратор)")
        print("  - doctor / doctor123 (Врач)")
        print("  - registrar / registrar123 (Регистратор)")
        print(f"✅ Создан отдел: {general_dept.name_ru}")
        print(f"✅ Создан профиль врача для {doctor_user.full_name}")

except Exception as e:
    print(f"❌ Ошибка при создании пользователей: {e}")
    db.rollback()
finally:
    db.close()

print("🎉 Инициализация базы данных завершена!")

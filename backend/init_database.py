#!/usr/bin/env python3
"""
Скрипт для инициализации базовых данных.
Схема должна быть создана миграциями Alembic до запуска этого seed-helper.
"""

import os
import sys
from datetime import time
from pathlib import Path

# Добавляем путь к проекту
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def require_init_database_confirmation():
    if os.getenv("CONFIRM_INIT_DATABASE") != "1":
        raise RuntimeError(
            "Refusing to initialize database seed data. "
            "Run Alembic migrations first and set CONFIRM_INIT_DATABASE=1 only for an explicit bootstrap run."
        )


require_init_database_confirmation()

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.user import User
from app.models.role_permission import Role, Permission, UserGroup
from app.models.authentication import RefreshToken, UserActivity, SecurityEvent, LoginAttempt
from app.models.department import Department
from app.models.clinic import Doctor
from app.core.config import settings
from passlib.context import CryptContext

# Создаем движок базы данных
def _database_url() -> str:
    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before initializing seed data.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("init_database.py requires PostgreSQL with Alembic-applied schema.")
    return database_url


def _password_env_names(username: str) -> list[str]:
    names = [f"INIT_DATABASE_{username.upper()}_PASSWORD"]
    if username == "admin":
        names.insert(0, "ADMIN_PASSWORD")
    return names


def _required_password(username: str) -> str:
    for env_name in _password_env_names(username):
        password = os.getenv(env_name, "").strip()
        if password:
            return password
    expected = " or ".join(_password_env_names(username))
    raise RuntimeError(f"Set {expected} before initializing user '{username}'.")


engine = create_engine(_database_url(), echo=True)

# Создаем контекст для хеширования паролей
# Используем argon2 как основной (как настроено в security.py), bcrypt как запасной
pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


# Создаем сессию
print("👥 Создание базовых пользователей...")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
db = SessionLocal()

try:
    # Проверяем, есть ли уже пользователи
    existing_users = db.query(User).count()
    if existing_users > 0:
        print(f"✅ В базе уже есть {existing_users} пользователей")
    else:
        passwords = {
            "admin": _required_password("admin"),
            "doctor": _required_password("doctor"),
            "registrar": _required_password("registrar"),
        }

        # Создаем роли (используем правильную модель Role из role_permission.py)
        admin_role = Role(
            name="Admin",
            display_name="Администратор",
            description="Администратор системы",
            level=100,
            is_system=True,
        )
        doctor_role = Role(
            name="Doctor",
            display_name="Врач",
            description="Врач",
            level=50,
            is_system=True,
        )
        registrar_role = Role(
            name="Registrar",
            display_name="Регистратор",
            description="Регистратор",
            level=30,
            is_system=True,
        )

        db.add_all([admin_role, doctor_role, registrar_role])
        db.flush()  # Получаем ID ролей

        # Создаем пользователей
        admin_user = User(
            username="admin",
            email="admin@clinic.local",
            full_name="Администратор",
            hashed_password=get_password_hash(passwords["admin"]),
            role="Admin",
            is_active=True,
            is_superuser=True,
        )

        doctor_user = User(
            username="doctor",
            email="doctor@clinic.local",
            full_name="Доктор Иванов",
            hashed_password=get_password_hash(passwords["doctor"]),
            role="Doctor",
            is_active=True,
            is_superuser=False,
        )

        registrar_user = User(
            username="registrar",
            email="registrar@clinic.local",
            full_name="Регистратор Петрова",
            hashed_password=get_password_hash(passwords["registrar"]),
            role="Registrar",
            is_active=True,
            is_superuser=False,
        )

        users = [admin_user, doctor_user, registrar_user]
        db.add_all(users)
        db.flush()  # Получаем ID пользователей

        # Создаем отделение (критически важно для работы QR Queue)
        general_dept = Department(
            key="general",
            name_ru="Общее отделение",
            name_uz="Umumiy bo'lim",
            icon="folder",
            display_order=1,
            active=True,
            description="Общее отделение клиники",
        )
        db.add(general_dept)
        db.flush()  # Получаем ID отделения

        # Создаем профиль врача (Doctor) - связывает User с отделением
        # Это критически важно для работы QR Queue системы!
        doctor = Doctor(
            user_id=doctor_user.id,
            department_id=general_dept.id,
            specialty="general",
            active=True,
            start_number_online=1,
            max_online_per_day=20,
            # Store a typed time value instead of a string.
            auto_close_time=time(9, 0),
        )
        db.add(doctor)

        db.commit()

        print("✅ Созданы роли:")
        print("  - Admin (уровень 100)")
        print("  - Doctor (уровень 50)")
        print("  - Registrar (уровень 30)")
        print()
        print("✅ Созданы пользователи:")
        print("  - admin (Администратор)")
        print("  - doctor (Врач)")
        print("  - registrar (Регистратор)")
        print()
        print(f"✅ Создано отделение: {general_dept.name_ru} (key={general_dept.key})")
        print(f"✅ Создан профиль врача для {doctor_user.full_name} (Doctor.id={doctor.id})")
        print()
        print("💡 Теперь QR Queue система сможет находить очереди по doctor.id")

except Exception as e:
    print(f"❌ Ошибка при создании пользователей: {e}")
    import traceback
    traceback.print_exc()
    db.rollback()
finally:
    db.close()

print()
print("🎉 Инициализация базы данных завершена!")

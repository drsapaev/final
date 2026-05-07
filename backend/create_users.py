#!/usr/bin/env python3
"""
Скрипт для создания пользователей с разными ролями
"""

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def require_create_users_confirmation():
    if os.getenv("CONFIRM_CREATE_USERS") != "1":
        raise RuntimeError(
            "Refusing to create users. "
            "Set CONFIRM_CREATE_USERS=1 only for an explicit local bootstrap run."
        )


def require_postgres_database_url():
    from app.core.config import settings

    database_url = str(settings.DATABASE_URL).strip()
    if not database_url:
        raise RuntimeError("DATABASE_URL must be set before creating users.")
    if database_url.lower().startswith("sqlite"):
        raise RuntimeError("create_users.py requires PostgreSQL; SQLite is not allowed.")


def create_users():
    """Создание пользователей с разными ролями"""
    require_create_users_confirmation()
    require_postgres_database_url()

    db = SessionLocal()
    try:
        # Список пользователей для создания
        users_data = [
            {
                "username": "admin",
                "password": "admin123",
                "role": "Admin",
                "full_name": "Administrator",
            },
            {
                "username": "registrar",
                "password": "registrar123",
                "role": "Registrar",
                "full_name": "Регистратор",
            },
            {
                "username": "doctor",
                "password": "doctor123",
                "role": "Doctor",
                "full_name": "Врач",
            },
            {
                "username": "cashier",
                "password": "cashier123",
                "role": "Cashier",
                "full_name": "Кассир",
            },
            {
                "username": "lab",
                "password": "lab123",
                "role": "Lab",
                "full_name": "Лаборант",
            },
            {
                "username": "cardio",
                "password": "cardio123",
                "role": "Doctor",
                "full_name": "Кардиолог",
            },
            {
                "username": "derma",
                "password": "derma123",
                "role": "Doctor",
                "full_name": "Дерматолог",
            },
            {
                "username": "dentist",
                "password": "dentist123",
                "role": "Doctor",
                "full_name": "Стоматолог",
            },
        ]

        for user_data in users_data:
            # Проверяем, существует ли пользователь
            existing_user = (
                db.query(User).filter(User.username == user_data["username"]).first()
            )
            if existing_user:
                print(f"✅ Пользователь {user_data['username']} уже существует")
                continue

            # Создаём пользователя
            user = User(
                username=user_data["username"],
                full_name=user_data["full_name"],
                email=f"{user_data['username']}@clinic.local",
                hashed_password=get_password_hash(user_data["password"]),
                role=user_data["role"],
                is_active=True,
            )

            db.add(user)
            print(
                f"✅ Создан пользователь {user_data['username']} с паролем {user_data['password']}"
            )

        db.commit()
        print("\n✅ Все пользователи успешно созданы!")

    except Exception as e:
        print(f"❌ Ошибка при создании пользователей: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_users()

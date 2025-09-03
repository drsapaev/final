#!/usr/bin/env python3
"""
Простой скрипт для создания пользователя admin
"""

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def create_admin():
    """Создание пользователя admin"""
    db = SessionLocal()
    try:
        # Проверяем, существует ли уже админ
        existing_admin = db.query(User).filter(User.username == "admin").first()
        if existing_admin:
            print("✅ Пользователь admin уже существует")
            print(f"   Роль: {existing_admin.role}")
            print(f"   Активен: {existing_admin.is_active}")
            return

        # Создаём администратора
        admin_user = User(
            username="admin",
            full_name="Administrator",
            email="admin@clinic.local",
            hashed_password=get_password_hash("admin"),
            role="Admin",
            is_active=True,
        )

        db.add(admin_user)
        db.commit()

        print("✅ Пользователь admin успешно создан")
        print("   Логин: admin")
        print("   Пароль: admin")
        print("   Роль: Admin")

    except Exception as e:
        print(f"❌ Ошибка при создании администратора: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    create_admin()

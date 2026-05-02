#!/usr/bin/env python3
"""
Скрипт для сброса пароля администратора
"""

import os

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def _required_admin_password() -> str:
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("Set ADMIN_PASSWORD before resetting the admin password.")
    return password


def reset_admin_password():
    """Сброс пароля администратора на ADMIN_PASSWORD."""
    db = SessionLocal()
    try:
        # Ищем пользователя admin
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            # Устанавливаем новый пароль
            new_password = _required_admin_password()
            admin_user.hashed_password = get_password_hash(new_password)
            db.commit()
            print(
                f"✅ Пароль для пользователя '{admin_user.username}' успешно сброшен"
            )
        else:
            print("❌ Пользователь 'admin' не найден")
    except Exception as e:
        print(f"❌ Ошибка при сбросе пароля: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    reset_admin_password()

#!/usr/bin/env python3
"""
Скрипт для сброса пароля администратора
"""

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def reset_admin_password():
    """Сброс пароля администратора на 'admin123'"""
    db = SessionLocal()
    try:
        # Ищем пользователя admin
        admin_user = db.query(User).filter(User.username == "admin").first()
        if admin_user:
            # Устанавливаем новый пароль
            new_password = "admin123"
            admin_user.hashed_password = get_password_hash(new_password)
            db.commit()
            print(
                f"✅ Пароль для пользователя '{admin_user.username}' успешно сброшен на '{new_password}'"
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

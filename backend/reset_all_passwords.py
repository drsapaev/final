#!/usr/bin/env python3
"""
Скрипт для сброса паролей всех пользователей
"""

from app.core.security import get_password_hash
from app.db.session import SessionLocal
from app.models.user import User


def reset_all_passwords():
    """Сброс паролей всех пользователей согласно документации"""
    db = SessionLocal()
    try:
        # Пользователи и их пароли согласно ROLES_AND_ROUTING.md
        users_data = [
            ("admin", "admin123"),
            ("registrar", "registrar123"),
            ("lab", "lab123"),
            ("doctor", "doctor123"),
            ("cashier", "cashier123"),
            ("cardio", "cardio123"),
            ("derma", "derma123"),
            ("dentist", "dentist123"),
        ]
        
        for username, password in users_data:
            user = db.query(User).filter(User.username == username).first()
            if user:
                # Устанавливаем новый пароль
                user.hashed_password = get_password_hash(password)
                print(f"✓ Пароль для {username} сброшен на {password}")
            else:
                print(f"✗ Пользователь {username} не найден")
        
        db.commit()
        print("\n✓ Все пароли успешно сброшены!")
        
    except Exception as e:
        print(f"✗ Ошибка при сбросе паролей: {e}")
        db.rollback()
    finally:
        db.close()


if __name__ == "__main__":
    reset_all_passwords()

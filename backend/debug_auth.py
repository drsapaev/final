#!/usr/bin/env python3
"""
Скрипт для отладки аутентификации
"""

import sqlite3
from app.core.security import verify_password
from app.db.session import SessionLocal
from app.models.user import User
from sqlalchemy import select


def debug_auth():
    """Отладка аутентификации"""
    print("=== Отладка аутентификации ===")

    # 1. Проверим пользователя в БД напрямую
    print("\n1. Проверка пользователя в БД через SQLite:")
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    cursor.execute(
        "SELECT username, hashed_password, is_active FROM users WHERE username = ?",
        ('admin',),
    )
    sqlite_user = cursor.fetchone()
    if sqlite_user:
        print(f"   Пользователь: {sqlite_user[0]}")
        print(f"   Хеш пароля: {sqlite_user[1][:50]}...")
        print(f"   Активен: {sqlite_user[2]}")
    else:
        print("   ❌ Пользователь не найден в SQLite")
        return
    conn.close()

    # 2. Проверим через SQLAlchemy
    print("\n2. Проверка через SQLAlchemy:")
    db = SessionLocal()
    try:
        stmt = select(User).where(User.username == "admin")
        result = db.execute(stmt)
        user = result.scalar_one_or_none()

        if user:
            print(f"   Пользователь найден: {user.username}")
            print(f"   Хеш пароля: {user.hashed_password[:50]}...")
            print(f"   Активен: {user.is_active}")

            # 3. Проверим пароль
            print("\n3. Проверка пароля:")
            test_passwords = ['admin', 'admin123', 'password']
            for pwd in test_passwords:
                is_valid = verify_password(pwd, user.hashed_password)
                print(
                    f"   Пароль '{pwd}': {'✅ Верный' if is_valid else '❌ Неверный'}"
                )

        else:
            print("   ❌ Пользователь не найден через SQLAlchemy")

    except Exception as e:
        print(f"   ❌ Ошибка SQLAlchemy: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    debug_auth()

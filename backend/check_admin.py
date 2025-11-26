#!/usr/bin/env python3
"""
Скрипт для проверки пароля администратора
"""

import sqlite3
from app.core.security import verify_password


def check_admin_password():
    """Проверка пароля администратора"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()

    try:
        # Получаем хеш пароля admin
        cursor.execute(
            "SELECT username, hashed_password FROM users WHERE username = ?", ('admin',)
        )
        result = cursor.fetchone()

        if result:
            username, hashed_password = result
            print(f"Пользователь: {username}")
            print(f"Хеш пароля: {hashed_password}")

            # Проверяем разные пароли
            test_passwords = ['admin', 'admin123', 'password', '123456']

            for password in test_passwords:
                if verify_password(password, hashed_password):
                    print(f"✅ Правильный пароль: {password}")
                    return password
                else:
                    print(f"❌ Неправильный пароль: {password}")

            print("❌ Ни один из тестовых паролей не подошел")
        else:
            print("❌ Пользователь admin не найден")

    except Exception as e:
        print(f"Ошибка: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    check_admin_password()

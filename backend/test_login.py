#!/usr/bin/env python3
"""
Скрипт для тестирования логина
"""

import requests


def test_login():
    """Тестирование логина"""
    try:
        # Сначала проверим, что пользователь существует в БД
        print("Проверяем пользователя в БД...")
        import sqlite3

        conn = sqlite3.connect('clinic.db')
        cursor = conn.cursor()
        cursor.execute(
            "SELECT username, role, is_active FROM users WHERE username = ?", ('admin',)
        )
        user = cursor.fetchone()
        if user:
            print(
                f"Пользователь найден: {user[0]}, роль: {user[1]}, активен: {user[2]}"
            )
        else:
            print("❌ Пользователь admin не найден в БД!")
            return
        conn.close()

        # Тестируем логин admin
        print("Тестируем логин через API...")
        response = requests.post(
            'http://localhost:8000/api/v1/auth/login',
            data={
                'username': 'admin',
                'password': 'admin123',
                'grant_type': 'password',
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
        )

        print(f"Login status: {response.status_code}")
        print(f"Response headers: {dict(response.headers)}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Login successful!")
            print(f"Token: {data.get('access_token', 'N/A')[:50]}...")
            print(f"Token type: {data.get('token_type', 'N/A')}")
        else:
            print(f"❌ Login failed: {response.text}")

    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    test_login()

#!/usr/bin/env python3
"""Простой тест авторизации и ролей"""

import requests
import json
from datetime import datetime, timedelta
from jose import jwt
from app.core.config import settings

def test_auth():
    # Тест 1: Проверяем токен
    print("🔍 Тест 1: Проверяем токен...")
    payload = {'sub': '19', 'user_id': 19, 'username': 'admin@example.com'}
    token = jwt.encode({**payload, 'exp': datetime.utcnow() + timedelta(hours=1)},
                      settings.SECRET_KEY,
                      algorithm=getattr(settings, 'ALGORITHM', 'HS256'))
    print(f"✅ Токен создан: {token[:50]}...")

    # Тест 2: Проверяем endpoint /auth/me
    print("\n🔍 Тест 2: Проверяем /auth/me...")
    headers = {'Authorization': f'Bearer {token}'}
    try:
        response = requests.get('http://localhost:18000/api/v1/auth/me', headers=headers)
        print(f"Статус: {response.status_code}")
        if response.status_code == 200:
            user_data = response.json()
            print(f"✅ Пользователь: {user_data.get('username')}")
            print(f"   ID: {user_data.get('id')}")
            print(f"   Роли: {user_data.get('roles', [])}")
        elif response.status_code == 401:
            print("❌ 401: Токен не валиден")
        else:
            print(f"❌ Ошибка: {response.text}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

    # Тест 3: Проверяем /admin/wizard-settings
    print("\n🔍 Тест 3: Проверяем /admin/wizard-settings...")
    try:
        response = requests.get('http://localhost:18000/api/v1/admin/wizard-settings', headers=headers)
        print(f"Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Настройки получены: {data}")
        elif response.status_code == 401:
            print("❌ 401: Нет доступа (требуется роль Admin/Registrar)")
        else:
            print(f"❌ Ошибка: {response.text}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

    # Тест 4: Проверяем /users/users
    print("\n🔍 Тест 4: Проверяем /users/users...")
    try:
        response = requests.get('http://localhost:18000/api/v1/users/users', headers=headers)
        print(f"Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Пользователи получены: {len(data.get('users', []))} пользователей")
        elif response.status_code == 401:
            print("❌ 401: Нет доступа (требуется роль Admin)")
        else:
            print(f"❌ Ошибка: {response.text}")
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")

if __name__ == "__main__":
    test_auth()

#!/usr/bin/env python3
"""
Тестовый скрипт для диагностики проблем фронтенда
"""

import requests
import json

def test_api_endpoints():
    """Тестируем все API эндпоинты, которые использует фронтенд"""

    base_url = "http://localhost:8000"
    token = None

    # 1. Получаем токен
    print("🔐 Получаем токен аутентификации...")
    try:
        response = requests.post(
            f"{base_url}/api/v1/auth/minimal-login",
            json={"username": "registrar@example.com", "password": "registrar123", "remember_me": False},
            timeout=5
        )
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"✅ Токен получен: {token[:30]}...")
        else:
            print(f"❌ Ошибка аутентификации: {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ Ошибка при аутентификации: {e}")
        return False

    if not token:
        print("❌ Не удалось получить токен")
        return False

    # 2. Тестируем эндпоинты регистратора
    endpoints = [
        "/api/v1/registrar/doctors",
        "/api/v1/registrar/services",
        "/api/v1/registrar/queue-settings",
        "/api/v1/registrar/queues/today"
    ]

    headers = {"Authorization": f"Bearer {token}"}

    print("\n🔍 Тестируем API эндпоинты регистратора...")
    all_success = True

    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", headers=headers, timeout=5)
            status = "✅" if response.status_code == 200 else "❌"
            print(f"{status} {endpoint}: {response.status_code}")

            if response.status_code != 200:
                all_success = False
                try:
                    error_data = response.json()
                    print(f"   Ошибка: {error_data}")
                except:
                    print(f"   Ошибка: {response.text}")
        except Exception as e:
            print(f"❌ {endpoint}: Ошибка подключения - {e}")
            all_success = False

    return all_success

if __name__ == "__main__":
    success = test_api_endpoints()
    if success:
        print("\n🎉 Все API эндпоинты работают корректно!")
    else:
        print("\n⚠️ Некоторые API эндпоинты недоступны")
    exit(0 if success else 1)

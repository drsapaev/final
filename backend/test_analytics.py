#!/usr/bin/env python3
"""
Тест расширенной аналитики
"""

import json
from datetime import datetime, timedelta

import requests

BASE_URL = "http://localhost:18000/api/v1"


def get_auth_token():
    """Получение токена авторизации"""
    login_data = {"username": "admin", "password": "admin123"}

    response = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        print(f"❌ Ошибка авторизации: {response.status_code}")
        return None


def test_analytics_endpoint(endpoint, params=None):
    """Тест эндпоинта аналитики"""
    token = get_auth_token()
    if not token:
        return False

    headers = {"Authorization": f"Bearer {token}"}

    try:
        response = requests.get(
            f"{BASE_URL}/analytics/{endpoint}", headers=headers, params=params
        )

        if response.status_code == 200:
            data = response.json()
            print(f"✅ {endpoint}: {json.dumps(data, indent=2, ensure_ascii=False)}")
            return True
        else:
            print(f"❌ {endpoint}: {response.status_code} - {response.text}")
            return False

    except Exception as e:
        print(f"❌ {endpoint}: Ошибка - {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🧪 Тестирование расширенной аналитики")
    print("=" * 50)

    # Параметры для тестирования
    end_date = datetime.now()
    start_date = end_date - timedelta(days=30)

    params = {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
    }

    # Тестируем новые эндпоинты
    endpoints = [
        ("payment-providers", params),
        ("appointment-flow", params),
        ("revenue-breakdown", params),
    ]

    success_count = 0
    total_count = len(endpoints)

    for endpoint, endpoint_params in endpoints:
        print(f"\n📊 Тестирование {endpoint}...")
        if test_analytics_endpoint(endpoint, endpoint_params):
            success_count += 1

    print("\n📈 Результаты тестирования:")
    print(f"✅ Успешно: {success_count}/{total_count}")
    print(f"❌ Ошибок: {total_count - success_count}/{total_count}")

    if success_count == total_count:
        print("\n🎉 Все тесты пройдены успешно!")
    else:
        print("\n⚠️ Есть ошибки, проверьте логи выше")


if __name__ == "__main__":
    main()

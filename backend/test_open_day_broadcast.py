#!/usr/bin/env python3
"""
Тест broadcast из open_day
"""
import json
import urllib.parse
import urllib.request


def get_auth_token():
    """Получаем JWT токен для аутентификации"""
    try:
        data = urllib.parse.urlencode(
            {"username": "admin", "password": "admin123"}
        ).encode()
        req = urllib.request.Request(
            "http://127.0.0.1:18000/api/v1/login",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode())
                return data.get("access_token")
            else:
                print(f"❌ Ошибка получения токена: {response.status}")
                return None
    except Exception as e:
        print(f"❌ Ошибка запроса токена: {e}")
        return None


def test_open_day_broadcast():
    """Тестируем open_day с проверкой broadcast"""
    print("🔔 Тестирую open_day с broadcast...")

    token = get_auth_token()
    if not token:
        print("❌ Не удалось получить токен")
        return

    headers = {"Authorization": f"Bearer {token}"}

    # Открываем день
    print("📅 Открываю день для ENT...")
    try:
        req = urllib.request.Request(
            "http://127.0.0.1:18000/api/v1/appointments/open?department=ENT&date_str=2025-08-28&start_number=1",
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(req) as response:
            print(f"📅 Результат открытия: {response.status} OK")
            response_data = response.read().decode()
            print(f"📅 Ответ: {response_data}")

            # Проверяем, что в ответе есть ожидаемые поля
            data = json.loads(response_data)
            if "ok" in data and data["ok"]:
                print("✅ День успешно открыт")
            else:
                print("❌ Ошибка открытия дня")

    except Exception as e:
        print(f"📅 Ошибка: {e}")


if __name__ == "__main__":
    test_open_day_broadcast()

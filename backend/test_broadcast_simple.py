#!/usr/bin/env python3
"""
Простой тест broadcast без WebSocket
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


def test_broadcast_simple():
    """Тестируем broadcast просто"""
    print("🔔 Тестирую broadcast просто...")
    print("🔔 Ожидаю логи broadcast в консоли сервера...")

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
                print("🔔 Проверьте консоль сервера на наличие логов broadcast")
                print("🔔 Должны быть логи:")
                print("   - '🔔 Attempting to import _broadcast...'")
                print("   - '🔔 _broadcast imported successfully'")
                print("   - '🔔 Calling _broadcast(ENT, 2025-08-28, stats)'")
                print("   - '🔔 _broadcast called successfully'")
            else:
                print("❌ Ошибка открытия дня")

    except Exception as e:
        print(f"📅 Ошибка: {e}")


if __name__ == "__main__":
    test_broadcast_simple()

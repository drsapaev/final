#!/usr/bin/env python3
"""
Тест одного эндпоинта с детальным логированием
"""
import json
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def test_transactions_endpoint():
    """Тестируем эндпоинт транзакций"""
    print("🚀 Тест эндпоинта транзакций")
    print("=" * 50)

    # Шаг 1: Логин
    print("🔑 Получаем токен...")
    login_url = f"{BASE_URL}/api/v1/auth/login"
    login_data = {"username": "admin", "password": "admin123"}

    try:
        form_data = urllib.parse.urlencode(login_data).encode("utf-8")
        req = urllib.request.Request(login_url, data=form_data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                token_data = json.loads(response_text)
                token = token_data["access_token"]
                print("✅ Токен получен")
            else:
                print(f"❌ Ошибка логина: {response.read().decode('utf-8')}")
                return
    except Exception as e:
        print(f"❌ Ошибка логина: {e}")
        return

    # Шаг 2: Тест эндпоинта транзакций
    print("\n💳 Тестируем эндпоинт транзакций...")

    # Пробуем разные варианты URL
    urls_to_test = [
        f"{BASE_URL}/api/v1/webhooks/webhooks/payment/transactions",
        f"{BASE_URL}/api/v1/webhooks/webhooks/payment/transactions?skip=0&limit=10",
        f"{BASE_URL}/api/v1/webhooks/webhooks/payment/transactions?skip=0&limit=1",
    ]

    for i, url in enumerate(urls_to_test, 1):
        print(f"\n🔍 Тест {i}: {url}")

        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", f"Bearer {token}")
            req.add_header("Accept", "application/json")

            with urllib.request.urlopen(req) as response:
                print(f"📡 Статус: {response.status}")
                print(f"📋 Заголовки: {dict(response.headers)}")

                response_text = response.read().decode("utf-8")
                print(f"📄 Ответ: {response_text}")

                if response.status == 200:
                    try:
                        data = json.loads(response_text)
                        print(f"✅ JSON парсинг успешен: {type(data)}")
                        if isinstance(data, list):
                            print(f"📊 Количество элементов: {len(data)}")
                    except json.JSONDecodeError as e:
                        print(f"❌ Ошибка JSON парсинга: {e}")
                else:
                    print(f"❌ HTTP ошибка: {response.status}")

        except Exception as e:
            print(f"❌ Ошибка запроса: {e}")
            if hasattr(e, "code"):
                print(f"📡 HTTP код: {e.code}")
            if hasattr(e, "read"):
                try:
                    error_text = e.read().decode("utf-8")
                    print(f"📄 Текст ошибки: {error_text}")
                except Exception:
                    pass


if __name__ == "__main__":
    test_transactions_endpoint()

#!/usr/bin/env python3
"""
Скрипт для тестирования вебхуков оплат
"""
import json
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def test_payme_webhook():
    """Тестируем вебхук от Payme"""
    print("🧪 Тестируем вебхук от Payme...")

    url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment/payme"
    headers = {
        "Content-Type": "application/json",
        "X-Payme-Signature": "test_signature",
    }
    data = {"id": "test_123", "state": 1, "amount": 50000}

    try:
        # Подготавливаем запрос
        req = urllib.request.Request(
            url, data=json.dumps(data).encode("utf-8"), headers=headers
        )

        # Отправляем запрос
        with urllib.request.urlopen(req) as response:
            response_text = response.read().decode("utf-8")
            print(f"📡 Статус: {response.status}")
            print(f"📄 Ответ: {response_text}")

            if response.status == 200:
                result = json.loads(response_text)
                if result.get("ok"):
                    print("✅ Вебхук успешно обработан!")
                else:
                    print(f"⚠️ Вебхук обработан с ошибкой: {result.get('message')}")
            else:
                print(f"❌ Ошибка HTTP: {response.status}")

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")


def test_click_webhook():
    """Тестируем вебхук от Click"""
    print("\n🧪 Тестируем вебхук от Click...")

    url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment/click"
    data = {
        "click_trans_id": "test_click_456",
        "merchant_trans_id": "visit_789",
        "amount": "500.00",
        "action": "0",
        "error": "",
        "sign_time": "1234567890",
        "sign_string": "test_sign",
    }

    try:
        # Подготавливаем данные формы
        form_data = urllib.parse.urlencode(data).encode("utf-8")

        # Создаём запрос
        req = urllib.request.Request(url, data=form_data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        # Отправляем запрос
        with urllib.request.urlopen(req) as response:
            response_text = response.read().decode("utf-8")
            print(f"📡 Статус: {response.status}")
            print(f"📄 Ответ: {response_text}")

            if response.status == 200:
                result = json.loads(response_text)
                if result.get("ok"):
                    print("✅ Вебхук успешно обработан!")
                else:
                    print(f"⚠️ Вебхук обработан с ошибкой: {result.get('message')}")
            else:
                print(f"❌ Ошибка HTTP: {response.status}")

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")


def test_providers_list():
    """Тестируем список провайдеров"""
    print("\n🧪 Тестируем список провайдеров...")

    # Сначала получаем токен
    login_url = f"{BASE_URL}/api/v1/auth/login"
    login_data = {"username": "admin", "password": "admin123"}

    try:
        # Подготавливаем данные логина
        form_data = urllib.parse.urlencode(login_data).encode("utf-8")

        # Создаём запрос логина
        login_req = urllib.request.Request(login_url, data=form_data)
        login_req.add_header("Content-Type", "application/x-www-form-urlencoded")

        # Отправляем запрос логина
        with urllib.request.urlopen(login_req) as response:
            if response.status == 200:
                login_response_text = response.read().decode("utf-8")
                token_data = json.loads(login_response_text)
                token = token_data["access_token"]
                print("🔑 Токен получен")

                # Теперь получаем список провайдеров
                providers_url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment/providers"

                # Создаём запрос с токеном
                providers_req = urllib.request.Request(providers_url)
                providers_req.add_header("Authorization", f"Bearer {token}")

                # Отправляем запрос
                with urllib.request.urlopen(providers_req) as providers_response:
                    print(f"📡 Статус: {providers_response.status}")

                    if providers_response.status == 200:
                        providers_text = providers_response.read().decode("utf-8")
                        providers = json.loads(providers_text)
                        print(f"📋 Найдено провайдеров: {len(providers)}")
                        for provider in providers:
                            status = (
                                "🟢 Активен"
                                if provider["is_active"]
                                else "🔴 Неактивен"
                            )
                            print(
                                f"  - {provider['name']} ({provider['code']}): {status}"
                            )
                    else:
                        print(f"❌ Ошибка: {providers_response.read().decode('utf-8')}")
            else:
                print(f"❌ Ошибка логина: {response.read().decode('utf-8')}")

    except Exception as e:
        print(f"❌ Ошибка: {e}")


if __name__ == "__main__":
    print("🚀 Тестирование вебхуков оплат")
    print("=" * 50)

    test_payme_webhook()
    test_click_webhook()
    test_providers_list()

    print("\n🎉 Тестирование завершено!")

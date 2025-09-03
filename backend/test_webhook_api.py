#!/usr/bin/env python3
"""
Тест API эндпоинтов вебхуков
"""
import json
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def test_login():
    """Тестируем логин"""
    print("🔑 Тестируем логин...")

    login_url = f"{BASE_URL}/api/v1/auth/login"
    login_data = {"username": "admin", "password": "admin"}

    try:
        form_data = urllib.parse.urlencode(login_data).encode("utf-8")
        req = urllib.request.Request(login_url, data=form_data)
        req.add_header("Content-Type", "application/x-www-form-urlencoded")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                token_data = json.loads(response_text)
                token = token_data["access_token"]
                print("✅ Логин успешен")
                return token
            else:
                print(f"❌ Ошибка логина: {response.read().decode('utf-8')}")
                return None
    except Exception as e:
        print(f"❌ Ошибка логина: {e}")
        return None


def test_webhook_list(token):
    """Тестируем список вебхуков"""
    print("\n📋 Тестируем список вебхуков...")

    webhook_url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment"

    try:
        req = urllib.request.Request(webhook_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            print(f"📡 Статус: {response.status}")
            response_text = response.read().decode("utf-8")
            print(f"📄 Ответ: {response_text}")

            if response.status == 200:
                webhooks = json.loads(response_text)
                print(f"✅ Получено вебхуков: {len(webhooks)}")
                return True
            else:
                print(f"❌ Ошибка получения вебхуков")
                return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_transaction_list(token):
    """Тестируем список транзакций"""
    print("\n💳 Тестируем список транзакций...")

    transaction_url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment/transactions"

    try:
        req = urllib.request.Request(transaction_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            print(f"📡 Статус: {response.status}")
            response_text = response.read().decode("utf-8")
            print(f"📄 Ответ: {response_text}")

            if response.status == 200:
                transactions = json.loads(response_text)
                print(f"✅ Получено транзакций: {len(transactions)}")
                return True
            else:
                print(f"❌ Ошибка получения транзакций")
                return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def test_webhook_summary(token):
    """Тестируем сводку вебхуков"""
    print("\n📊 Тестируем сводку вебхуков...")

    summary_url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment/summary"

    try:
        req = urllib.request.Request(summary_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            print(f"📡 Статус: {response.status}")
            response_text = response.read().decode("utf-8")
            print(f"📄 Ответ: {response_text}")

            if response.status == 200:
                summary = json.loads(response_text)
                print(f"✅ Сводка получена")
                return True
            else:
                print(f"❌ Ошибка получения сводки")
                return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 Тест API эндпоинтов вебхуков")
    print("=" * 50)

    # Шаг 1: Логин
    token = test_login()
    if not token:
        print("❌ Тест прерван: не удалось авторизоваться")
        return

    # Шаг 2: Тест списка вебхуков
    test_webhook_list(token)

    # Шаг 3: Тест списка транзакций
    test_transaction_list(token)

    # Шаг 4: Тест сводки
    test_webhook_summary(token)

    print("\n" + "=" * 50)
    print("🎉 Тест API завершён!")


if __name__ == "__main__":
    main()

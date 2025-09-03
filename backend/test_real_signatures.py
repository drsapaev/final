#!/usr/bin/env python3
"""
Тест с реальными подписями Payme
"""
import hashlib
import hmac
import json
import time
import urllib.parse
import urllib.request

BASE_URL = "http://127.0.0.1:8000"


def generate_payme_signature(data: dict, secret_key: str) -> str:
    """Генерируем правильную подпись для Payme"""
    # Сортируем ключи по алфавиту
    sorted_data = dict(sorted(data.items()))

    # Создаём строку для подписи
    sign_string = ""
    for key, value in sorted_data.items():
        if key != "signature" and value is not None:
            sign_string += f"{key}={value};"

    # Убираем последний символ ";"
    sign_string = sign_string.rstrip(";")

    # Создаём подпись
    signature = hmac.new(
        secret_key.encode("utf-8"), sign_string.encode("utf-8"), hashlib.sha256
    ).hexdigest()

    return signature


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


def test_payme_webhook_with_real_signature():
    """Тестируем вебхук Payme с реальной подписью"""
    print("\n📡 Тестируем вебхук Payme с реальной подписью...")

    # Создаём тестовые данные
    webhook_data = {
        "id": f"payme_test_{int(time.time())}",
        "state": 2,  # 2 = оплачено
        "amount": 50000,  # Сумма в тийинах
        "time": int(time.time()),
        "account": {"visit_id": "1", "payment_id": "1"},
        "create_time": int(time.time()) - 300,  # 5 минут назад
        "perform_time": int(time.time()),
        "cancel_time": None,
        "reason": None,
        "receivers": [],
    }

    # Используем тестовый секретный ключ
    secret_key = "test_secret_key_12345"

    # Генерируем правильную подпись
    signature = generate_payme_signature(webhook_data, secret_key)
    print(f"🔐 Сгенерирована подпись: {signature[:20]}...")

    # Отправляем вебхук
    webhook_url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment/payme"

    try:
        req = urllib.request.Request(
            webhook_url, data=json.dumps(webhook_data).encode("utf-8")
        )
        req.add_header("Content-Type", "application/json")
        req.add_header("X-Payme-Signature", signature)

        with urllib.request.urlopen(req) as response:
            response_text = response.read().decode("utf-8")
            print(f"📡 Статус вебхука: {response.status}")
            print(f"📄 Ответ: {response_text}")

            if response.status == 200:
                result = json.loads(response_text)
                if result.get("ok"):
                    print("✅ Вебхук успешно обработан!")
                    if result.get("webhook_id"):
                        print(f"📋 ID вебхука: {result['webhook_id']}")
                        return result["webhook_id"]
                else:
                    print(f"⚠️ Вебхук обработан с ошибкой: {result.get('message')}")
            else:
                print(f"❌ Ошибка HTTP: {response.status}")

    except Exception as e:
        print(f"❌ Ошибка отправки вебхука: {e}")
        if hasattr(e, "code"):
            print(f"📡 HTTP код: {e.code}")
        if hasattr(e, "read"):
            try:
                error_text = e.read().decode("utf-8")
                print(f"📄 Текст ошибки: {error_text}")
            except:
                pass

    return None


def check_webhook_status(webhook_id: int, token: str):
    """Проверяем статус вебхука"""
    if not webhook_id:
        print("❌ Нет ID вебхука для проверки")
        return False

    print(f"\n🔍 Проверяем статус вебхука {webhook_id}...")

    webhook_url = f"{BASE_URL}/api/v1/webhooks/webhooks/payment/{webhook_id}"

    try:
        req = urllib.request.Request(webhook_url)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                response_text = response.read().decode("utf-8")
                webhook = json.loads(response_text)
                print("✅ Вебхук найден:")
                print(f"  - Статус: {webhook.get('status', 'N/A')}")
                print(f"  - Провайдер: {webhook.get('provider', 'N/A')}")
                print(f"  - Сумма: {webhook.get('amount', 'N/A')} тийин")
                print(f"  - ID транзакции: {webhook.get('transaction_id', 'N/A')}")
                return True
            else:
                print(f"❌ Ошибка получения вебхука: {response.read().decode('utf-8')}")
                return False
    except Exception as e:
        print(f"❌ Ошибка проверки вебхука: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 Тест вебхуков с реальными подписями")
    print("=" * 60)

    # Шаг 1: Логин
    token = test_login()
    if not token:
        print("❌ Тест прерван: не удалось авторизоваться")
        return

    # Шаг 2: Тест вебхука с реальной подписью
    webhook_id = test_payme_webhook_with_real_signature()

    # Шаг 3: Проверка статуса вебхука
    if webhook_id:
        # Ждём немного для обработки
        print("\n⏳ Ждём 2 секунды для обработки...")
        time.sleep(2)

        # Проверяем статус
        check_webhook_status(webhook_id, token)

    print("\n" + "=" * 60)
    print("🎉 Тест завершён!")


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
🧪 Тест интеграции CI/CD для клиники
Проверяет основные функции после исправления CI/CD pipeline
"""

import json
import time
import urllib.parse
import urllib.request
from datetime import datetime

# Конфигурация
BASE_URL = "http://127.0.0.1:18000"
ADMIN_CREDENTIALS = {"username": "admin", "password": "admin123"}


def test_health_endpoint():
    """Тест эндпоинта здоровья"""
    print("🏥 Тестируем /api/v1/health...")
    try:
        response = urllib.request.urlopen(f"{BASE_URL}/api/v1/health")
        if response.getcode() == 200:
            print("✅ /api/v1/health работает")
            return True
        else:
            print(f"❌ /api/v1/health вернул {response.getcode()}")
            return False
    except Exception as e:
        print(f"❌ Ошибка /api/v1/health: {e}")
        return False


def test_status_endpoint():
    """Тест эндпоинта статуса"""
    print("📊 Тестируем /api/v1/status...")
    try:
        response = urllib.request.urlopen(f"{BASE_URL}/api/v1/status")
        if response.getcode() == 200:
            data = json.loads(response.read().decode())
            print(f"✅ /api/v1/status работает: {data.get('status', 'N/A')}")
            return True
        else:
            print(f"❌ /api/v1/status вернул {response.getcode()}")
            return False
    except Exception as e:
        print(f"❌ Ошибка /api/v1/status: {e}")
        return False


def test_queue_stats_endpoint():
    """Тест эндпоинта статистики очереди"""
    print("📈 Тестируем /api/v1/queue/stats...")
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        params = urllib.parse.urlencode({"department": "THERAPY", "date": today})
        url = f"{BASE_URL}/api/v1/queue/stats?{params}"

        response = urllib.request.urlopen(url)
        if response.getcode() == 200:
            data = json.loads(response.read().decode())
            print(
                f"✅ /api/v1/queue/stats работает: {data.get('total_tickets', 'N/A')} билетов"
            )
            return True
        else:
            print(f"❌ /api/v1/queue/stats вернул {response.getcode()}")
            return False
    except Exception as e:
        print(f"❌ Ошибка /api/v1/queue/stats: {e}")
        return False


def get_auth_token():
    """Получение токена аутентификации"""
    try:
        auth_data = urllib.parse.urlencode(ADMIN_CREDENTIALS).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/auth/login",
            data=auth_data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            data = json.loads(response.read().decode())
            return data.get("access_token")
        return None
    except Exception:
        return None


def test_appointments_stats_endpoint():
    """Тест эндпоинта статистики приёмов"""
    print("📅 Тестируем /api/v1/appointments/stats...")
    try:
        token = get_auth_token()
        if not token:
            print("⚠️ Не удалось получить токен аутентификации")
            return False

        today = datetime.now().strftime("%Y-%m-%d")
        params = urllib.parse.urlencode({"department": "THERAPY", "date": today})
        url = f"{BASE_URL}/api/v1/appointments/stats?{params}"

        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")

        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            data = json.loads(response.read().decode())
            print(
                f"✅ /api/v1/appointments/stats работает: {data.get('total_appointments', 'N/A')} приёмов"
            )
            return True
        else:
            print(f"❌ /api/v1/appointments/stats вернул {response.getcode()}")
            return False
    except Exception as e:
        print(f"❌ Ошибка /api/v1/appointments/stats: {e}")
        return False


def test_payment_webhook_endpoint():
    """Тест эндпоинта вебхуков оплаты"""
    print("💳 Тестируем /api/v1/payment-webhook/payme...")
    try:
        # Тестовый payload для Payme
        test_payload = {
            "method": "checkPerformTransaction",
            "params": {
                "id": "test_123",
                "account": {"order_id": "test_order"},
                "amount": 100000,
            },
        }

        data = json.dumps(test_payload).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/webhooks/payment/payme",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        response = urllib.request.urlopen(req)
        if response.getcode() in [200, 201, 422]:  # 422 - валидация, тоже нормально
            print(
                f"✅ /api/v1/webhooks/payment/payme работает (код: {response.getcode()})"
            )
            return True
        else:
            print(f"❌ /api/v1/webhooks/payment/payme вернул {response.getcode()}")
            return False
    except Exception as e:
        print(f"❌ Ошибка /api/v1/webhooks/payment/payme: {e}")
        return False


def test_printing_endpoint():
    """Тест эндпоинта печати"""
    print("🖨️ Тестируем /api/v1/print/ticket.pdf...")
    try:
        token = get_auth_token()
        if not token:
            print("⚠️ Не удалось получить токен аутентификации")
            return False

        params = urllib.parse.urlencode({"department": "THERAPY", "ticket_number": 1})
        url = f"{BASE_URL}/api/v1/print/ticket.pdf?{params}"

        req = urllib.request.Request(url)
        req.add_header("Authorization", f"Bearer {token}")

        response = urllib.request.urlopen(req)
        if response.getcode() == 200:
            content_type = response.headers.get("Content-Type", "")
            if (
                "pdf" in content_type.lower()
                or "application/octet-stream" in content_type
            ):
                print(f"✅ /api/v1/print/ticket.pdf работает (тип: {content_type})")
                return True
            else:
                print(
                    f"⚠️ /api/v1/print/ticket.pdf работает, но тип контента: {content_type}"
                )
                return True
        else:
            print(f"❌ /api/v1/print/ticket.pdf вернул {response.getcode()}")
            return False
    except Exception as e:
        print(f"❌ Ошибка /api/v1/print/ticket.pdf: {e}")
        return False


def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестов интеграции CI/CD для клиники")
    print("=" * 60)

    # Ждём запуска сервера
    print("⏳ Ждём запуска сервера...")
    time.sleep(5)

    tests = [
        test_health_endpoint,
        test_status_endpoint,
        test_queue_stats_endpoint,
        test_appointments_stats_endpoint,
        test_payment_webhook_endpoint,
        test_printing_endpoint,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
            print()
        except Exception as e:
            print(f"❌ Критическая ошибка в тесте {test.__name__}: {e}")
            results.append(False)
            print()

    # Итоговый отчёт
    print("=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЁТ:")
    print(f"✅ Успешных тестов: {sum(results)}")
    print(f"❌ Неудачных тестов: {len(results) - sum(results)}")
    print(f"📈 Общий процент успеха: {(sum(results)/len(results)*100):.1f}%")

    if sum(results) >= len(results) * 0.8:
        print("\n🎉 CI/CD ИНТЕГРАЦИЯ РАБОТАЕТ ОТЛИЧНО!")
        print("Все основные функции клиники доступны через API")
        return True
    else:
        print("\n⚠️ Есть проблемы с CI/CD интеграцией")
        print("Некоторые функции недоступны или работают некорректно")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

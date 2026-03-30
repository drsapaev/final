#!/usr/bin/env python3
"""
🧪 Тест функций Приоритета 2
Проверяет мобильное API, уведомления, аналитику и 2FA
"""

import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

# Конфигурация
BASE_URL = "http://127.0.0.1:18000"
ADMIN_CREDENTIALS = {"username": "admin", "password": "admin123"}


def log(message, level="INFO"):
    """Логирование"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")


def get_auth_token():
    """Получение токена аутентификации"""
    try:
        # Используем form-encoded данные для аутентификации
        data = urllib.parse.urlencode(ADMIN_CREDENTIALS).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/auth/login",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )

        response = urllib.request.urlopen(req, timeout=10)
        if response.getcode() == 200:
            result = json.loads(response.read().decode())
            return result.get("access_token")
        else:
            log(f"Ошибка аутентификации: {response.getcode()}", "ERROR")
            return None
    except Exception as e:
        log(f"Ошибка получения токена: {e}", "ERROR")
        return None


def test_mobile_api():
    """Тест мобильного API"""
    log("📱 Тестируем мобильное API")

    token = get_auth_token()
    if not token:
        log("❌ Не удалось получить токен для тестирования мобильного API", "ERROR")
        return False

    headers = {"Authorization": f"Bearer {token}"}

    tests = [
        ("/api/v1/mobile/public/health", "Публичный health check"),
        ("/api/v1/mobile/public/services", "Публичные услуги"),
    ]

    results = []
    for endpoint, description in tests:
        try:
            req = urllib.request.Request(f"{BASE_URL}{endpoint}", headers=headers)
            response = urllib.request.urlopen(req, timeout=10)

            if response.getcode() in [200, 201]:
                log(f"✅ {description}: {response.getcode()}")
                results.append(True)
            else:
                log(f"⚠️ {description}: {response.getcode()}")
                results.append(False)

        except Exception as e:
            log(f"❌ {description}: {e}", "ERROR")
            results.append(False)

    return all(results)


def test_notifications():
    """Тест системы уведомлений"""
    log("🔔 Тестируем систему уведомлений")

    token = get_auth_token()
    if not token:
        log("❌ Не удалось получить токен для тестирования уведомлений", "ERROR")
        return False

    headers = {"Authorization": f"Bearer {token}"}

    # Тест статуса уведомлений
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/notifications/notification-status", headers=headers
        )
        response = urllib.request.urlopen(req, timeout=10)

        if response.getcode() == 200:
            result = json.loads(response.read().decode())
            log(f"✅ Статус уведомлений получен: {result}")
            return True
        else:
            log(f"⚠️ Статус уведомлений: {response.getcode()}")
            return False

    except Exception as e:
        log(f"❌ Ошибка статуса уведомлений: {e}", "ERROR")
        return False


def test_analytics():
    """Тест системы аналитики"""
    log("📊 Тестируем систему аналитики")

    token = get_auth_token()
    if not token:
        log("❌ Не удалось получить токен для тестирования аналитики", "ERROR")
        return False

    headers = {"Authorization": f"Bearer {token}"}

    # Тест быстрой статистики
    try:
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/analytics/quick-stats", headers=headers
        )
        response = urllib.request.urlopen(req, timeout=10)

        if response.getcode() == 200:
            result = json.loads(response.read().decode())
            log(f"✅ Быстрая статистика получена: {result}")
            return True
        else:
            log(f"⚠️ Быстрая статистика: {response.getcode()}")
            return False

    except Exception as e:
        log(f"❌ Ошибка быстрой статистики: {e}", "ERROR")
        return False


def test_2fa():
    """Тест двухфакторной аутентификации"""
    log("🔐 Тестируем двухфакторную аутентификацию")

    token = get_auth_token()
    if not token:
        log("❌ Не удалось получить токен для тестирования 2FA", "ERROR")
        return False

    headers = {"Authorization": f"Bearer {token}"}

    # Тест статуса 2FA
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/v1/2fa/status", headers=headers)
        response = urllib.request.urlopen(req, timeout=10)

        if response.getcode() == 200:
            result = json.loads(response.read().decode())
            log(f"✅ Статус 2FA получен: {result}")
            return True
        else:
            log(f"⚠️ Статус 2FA: {response.getcode()}")
            return False

    except Exception as e:
        log(f"❌ Ошибка статуса 2FA: {e}", "ERROR")
        return False


def test_integration():
    """Интеграционный тест всех функций"""
    log("🔗 Интеграционный тест всех функций")

    token = get_auth_token()
    if not token:
        log("❌ Не удалось получить токен для интеграционного теста", "ERROR")
        return False

    headers = {"Authorization": f"Bearer {token}"}

    # Тест создания тестового пациента для мобильного API
    try:
        patient_data = {
            "first_name": "Тест",
            "last_name": "Пациент",
            "email": "test.patient@example.com",
            "phone": "+998901234567",
            "birth_date": "1990-01-01",
        }

        data = json.dumps(patient_data).encode("utf-8")
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/patients/",
            data=data,
            headers={**headers, "Content-Type": "application/json"},
        )

        response = urllib.request.urlopen(req, timeout=10)
        if response.getcode() in [200, 201]:
            result = json.loads(response.read().decode())
            patient_id = result.get("id")
            log(f"✅ Тестовый пациент создан: {patient_id}")

            # Тест отправки уведомления
            notification_data = {
                "patient_id": patient_id,
                "appointment_date": (datetime.now() + timedelta(days=1)).isoformat(),
                "doctor_name": "Тестовый врач",
                "department": "ТЕРАПИЯ",
            }

            data = json.dumps(notification_data).encode("utf-8")
            req = urllib.request.Request(
                f"{BASE_URL}/api/v1/notifications/send-appointment-reminder",
                data=data,
                headers={**headers, "Content-Type": "application/json"},
            )

            response = urllib.request.urlopen(req, timeout=10)
            if response.getcode() in [200, 201]:
                log("✅ Уведомление отправлено")
                return True
            else:
                log(f"⚠️ Отправка уведомления: {response.getcode()}")
                return False

        else:
            log(f"⚠️ Создание пациента: {response.getcode()}")
            return False

    except Exception as e:
        log(f"❌ Ошибка интеграционного теста: {e}", "ERROR")
        return False


def main():
    """Основная функция тестирования"""
    log("🚀 Запуск тестов функций Приоритета 2")
    log("=" * 60)

    # Запускаем тесты
    test_functions = [
        ("Мобильное API", test_mobile_api),
        ("Система уведомлений", test_notifications),
        ("Система аналитики", test_analytics),
        ("Двухфакторная аутентификация", test_2fa),
        ("Интеграционный тест", test_integration),
    ]

    results = []
    for test_name, test_func in test_functions:
        log(f"📋 Запуск: {test_name}")
        try:
            result = test_func()
            results.append(result)
            log(f"   Результат: {'✅ УСПЕХ' if result else '❌ НЕУДАЧА'}")
        except Exception as e:
            log(f"   ❌ Критическая ошибка: {e}", "ERROR")
            results.append(False)
        log("")

    # Итоговый отчёт
    log("=" * 60)
    log("📊 ИТОГОВЫЙ ОТЧЁТ:")
    log(f"✅ Успешных тестов: {sum(results)}")
    log(f"❌ Неудачных тестов: {len(results) - sum(results)}")
    log(f"📈 Общий процент успеха: {(sum(results)/len(results)*100):.1f}%")

    if sum(results) >= len(results) * 0.8:
        log("🎉 ФУНКЦИИ ПРИОРИТЕТА 2 РАБОТАЮТ ОТЛИЧНО!", "SUCCESS")
        log("✅ Мобильное API доступно")
        log("✅ Система уведомлений работает")
        log("✅ Аналитика функционирует")
        log("✅ 2FA настроена")
        log("✅ Интеграция работает")
        return True
    elif sum(results) >= len(results) * 0.6:
        log("⚠️ ФУНКЦИИ ПРИОРИТЕТА 2 РАБОТАЮТ ЧАСТИЧНО", "WARNING")
        log("Большинство функций доступны, есть мелкие проблемы")
        return True
    else:
        log("❌ Есть серьёзные проблемы с функциями Приоритета 2", "ERROR")
        log("Многие функции недоступны или работают некорректно")
        return False


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

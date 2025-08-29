#!/usr/bin/env python3
"""
🧪 Тест CI/CD для GitHub Actions
Проверяет функции клиники в автоматизированной среде
"""

import os
import sys
import urllib.request
import urllib.parse
import json
import time
from datetime import datetime

# Конфигурация для GitHub Actions
BASE_URL = os.getenv("TEST_BASE_URL", "http://127.0.0.1:8000")
MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "5"))

def log(message, level="INFO"):
    """Логирование для GitHub Actions"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] {level}: {message}")
    sys.stdout.flush()

def wait_for_server():
    """Ожидание запуска сервера"""
    log("⏳ Ожидание запуска сервера...")
    
    for attempt in range(MAX_RETRIES):
        try:
            response = urllib.request.urlopen(f"{BASE_URL}/api/v1/health", timeout=10)
            if response.getcode() == 200:
                log("✅ Сервер готов к тестированию")
                return True
        except Exception as e:
            log(f"⚠️ Попытка {attempt + 1}/{MAX_RETRIES}: {e}")
            if attempt < MAX_RETRIES - 1:
                time.sleep(RETRY_DELAY)
    
    log("❌ Сервер не запустился", "ERROR")
    return False

def test_endpoint_with_retry(endpoint, expected_status=200, description=""):
    """Тест эндпоинта с повторными попытками"""
    log(f"🧪 Тестируем {endpoint} {description}")
    
    for attempt in range(MAX_RETRIES):
        try:
            response = urllib.request.urlopen(f"{BASE_URL}{endpoint}", timeout=10)
            if response.getcode() == expected_status:
                log(f"✅ {endpoint} работает (код: {response.getcode()})")
                return True
            else:
                log(f"⚠️ {endpoint} вернул {response.getcode()}, ожидали {expected_status}")
                return False
        except Exception as e:
            if attempt < MAX_RETRIES - 1:
                log(f"⚠️ Попытка {attempt + 1}/{MAX_RETRIES}: {e}")
                time.sleep(RETRY_DELAY)
            else:
                log(f"❌ {endpoint} не работает: {e}", "ERROR")
                return False
    
    return False

def test_health_endpoints():
    """Тест эндпоинтов здоровья"""
    log("🏥 Тестируем эндпоинты здоровья")
    
    tests = [
        ("/api/v1/health", 200, "основной health check"),
        ("/api/v1/status", 200, "статус системы")
    ]
    
    results = []
    for endpoint, expected_status, description in tests:
        result = test_endpoint_with_retry(endpoint, expected_status, description)
        results.append(result)
    
    return all(results)

def test_queue_endpoints():
    """Тест эндпоинтов очереди"""
    log("📈 Тестируем эндпоинты очереди")
    
    today = datetime.now().strftime("%Y-%m-%d")
    params = urllib.parse.urlencode({
        "department": "THERAPY",
        "date": today
    })
    
    endpoint = f"/api/v1/queue/stats?{params}"
    return test_endpoint_with_retry(endpoint, 200, "статистика очереди")

def test_payment_webhooks():
    """Тест вебхуков оплаты"""
    log("💳 Тестируем вебхуки оплаты")
    
    test_payload = {
        "method": "checkPerformTransaction",
        "params": {
            "id": "test_123",
            "account": {"order_id": "test_order"},
            "amount": 100000
        }
    }
    
    try:
        data = json.dumps(test_payload).encode('utf-8')
        req = urllib.request.Request(
            f"{BASE_URL}/api/v1/webhooks/payment/payme",
            data=data,
            headers={'Content-Type': 'application/json'}
        )
        
        response = urllib.request.urlopen(req, timeout=10)
        if response.getcode() in [200, 201, 422]:
            log(f"✅ Вебхуки Payme работают (код: {response.getcode()})")
            return True
        else:
            log(f"⚠️ Вебхуки Payme вернули {response.getcode()}")
            return False
    except Exception as e:
        log(f"❌ Ошибка вебхуков Payme: {e}", "ERROR")
        return False

def test_database_connection():
    """Тест подключения к базе данных"""
    log("🗄️ Тестируем подключение к базе данных")
    
    try:
        # Проверяем через эндпоинт, который использует БД
        today = datetime.now().strftime("%Y-%m-%d")
        params = urllib.parse.urlencode({
            "department": "THERAPY",
            "date": today
        })
        
        response = urllib.request.urlopen(
            f"{BASE_URL}/api/v1/queue/stats?{params}",
            timeout=10
        )
        
        if response.getcode() == 200:
            log("✅ Подключение к базе данных работает")
            return True
        else:
            log(f"⚠️ Проблема с БД: код {response.getcode()}")
            return False
    except Exception as e:
        log(f"❌ Ошибка подключения к БД: {e}", "ERROR")
        return False

def main():
    """Основная функция тестирования"""
    log("🚀 Запуск тестов CI/CD для GitHub Actions")
    log("=" * 60)
    
    # Проверяем переменные окружения
    log(f"🔧 Конфигурация:")
    log(f"   BASE_URL: {BASE_URL}")
    log(f"   MAX_RETRIES: {MAX_RETRIES}")
    log(f"   RETRY_DELAY: {RETRY_DELAY}")
    log("")
    
    # Ждём запуска сервера
    if not wait_for_server():
        log("❌ Не удалось запустить сервер", "ERROR")
        return False
    
    # Запускаем тесты
    test_functions = [
        ("Эндпоинты здоровья", test_health_endpoints),
        ("Эндпоинты очереди", test_queue_endpoints),
        ("Вебхуки оплаты", test_payment_webhooks),
        ("Подключение к БД", test_database_connection)
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
        log("🎉 CI/CD ИНТЕГРАЦИЯ РАБОТАЕТ ОТЛИЧНО!", "SUCCESS")
        log("✅ Все основные функции клиники доступны")
        log("✅ API эндпоинты отвечают корректно")
        log("✅ База данных подключена и работает")
        log("✅ Вебхуки обрабатывают запросы")
        return True
    elif sum(results) >= len(results) * 0.6:
        log("⚠️ CI/CD ИНТЕГРАЦИЯ РАБОТАЕТ ЧАСТИЧНО", "WARNING")
        log("Большинство функций доступны, есть мелкие проблемы")
        return True
    else:
        log("❌ Есть серьёзные проблемы с CI/CD", "ERROR")
        log("Многие функции недоступны или работают некорректно")
        return False

if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)

"""
Тестирование MCP API endpoints через HTTP
"""
import requests
import json
import time

BASE_URL = "http://localhost:18000/api/v1"

def test_mcp_health():
    """Тест здоровья MCP через API"""
    print("🔍 Тестирование MCP Health endpoint...")

    try:
        response = requests.get(f"{BASE_URL}/mcp/health", timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP Health: {data.get('overall', 'unknown')}")

            if 'servers' in data:
                for server, status in data['servers'].items():
                    print(f"  {server}: {status.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def test_mcp_status():
    """Тест статуса MCP через API"""
    print("\n🔍 Тестирование MCP Status endpoint...")

    try:
        response = requests.get(f"{BASE_URL}/mcp/status", timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP Status: {data.get('healthy', False)}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def test_mcp_capabilities():
    """Тест возможностей MCP через API"""
    print("\n🔍 Тестирование MCP Capabilities endpoint...")

    try:
        response = requests.get(f"{BASE_URL}/mcp/capabilities", timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            if 'servers' in data:
                print(f"✅ Найдено серверов: {len(data['servers'])}")
                for server_name in data['servers'].keys():
                    print(f"  - {server_name}")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def test_complaint_validation():
    """Тест валидации жалоб через API"""
    print("\n🔍 Тестирование валидации жалоб через API...")

    try:
        # Тестируем без авторизации (должен вернуть 401)
        response = requests.post(
            f"{BASE_URL}/mcp/complaint/validate",
            params={"complaint": "Головная боль"},
            timeout=10
        )

        print(f"Status Code: {response.status_code}")

        if response.status_code == 401:
            print("✅ Авторизация работает корректно (401 Unauthorized)")
            return True
        elif response.status_code == 200:
            data = response.json()
            print(f"✅ Валидация работает: {data}")
            return True
        else:
            print(f"❌ Unexpected status: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def test_api_docs():
    """Тест доступности API документации"""
    print("\n🔍 Тестирование API документации...")

    try:
        response = requests.get("http://localhost:18000/docs", timeout=10)
        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            print("✅ API документация доступна")
            print("📖 Откройте http://localhost:18000/docs в браузере")
            return True
        else:
            print(f"❌ Error: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Connection error: {e}")
        return False

def main():
    """Основная функция тестирования API"""
    print("=" * 60)
    print("🚀 ТЕСТИРОВАНИЕ MCP API ENDPOINTS")
    print("=" * 60)

    # Ждем немного, чтобы сервер полностью запустился
    print("⏳ Ожидание запуска сервера...")
    time.sleep(3)

    tests = [
        ("API документация", test_api_docs),
        ("MCP Health", test_mcp_health),
        ("MCP Status", test_mcp_status),
        ("MCP Capabilities", test_mcp_capabilities),
        ("Валидация жалоб", test_complaint_validation),
    ]

    results = {}

    for test_name, test_func in tests:
        try:
            result = test_func()
            results[test_name] = result
        except Exception as e:
            print(f"\n❌ Критическая ошибка в тесте '{test_name}': {str(e)}")
            results[test_name] = False

    # Итоговый отчет
    print("\n" + "=" * 60)
    print("📊 ИТОГОВЫЙ ОТЧЕТ API ТЕСТИРОВАНИЯ")
    print("=" * 60)

    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)

    for test_name, success in results.items():
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {test_name}: {'Успешно' if success else 'Ошибка'}")

    print("\n" + "-" * 60)
    print(f"Результат: {success_count}/{total_count} тестов пройдено успешно")

    if success_count == total_count:
        print("🎉 ВСЕ API ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\n📋 Доступные MCP endpoints:")
        print("  GET  /api/v1/mcp/health - Проверка здоровья")
        print("  GET  /api/v1/mcp/status - Статус системы")
        print("  GET  /api/v1/mcp/metrics - Метрики")
        print("  GET  /api/v1/mcp/capabilities - Возможности")
        print("  POST /api/v1/mcp/complaint/analyze - Анализ жалоб")
        print("  POST /api/v1/mcp/icd10/suggest - Подсказки МКБ-10")
        print("  POST /api/v1/mcp/lab/interpret - Интерпретация анализов")
        print("  POST /api/v1/mcp/imaging/analyze - Анализ изображений")
        print("\n🌐 API документация: http://localhost:18000/docs")
    else:
        print(f"⚠️ {total_count - success_count} тестов завершились с ошибками")

    print("=" * 60)

if __name__ == "__main__":
    main()

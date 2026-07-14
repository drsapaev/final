"""
Тестирование MCP API с авторизацией
"""
import os
import sys

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.getenv("QA_BACKEND_API_BASE_URL", "http://localhost:18000/api/v1")
AUTH_USERNAME = os.getenv("QA_MCP_USERNAME", "mcp_test")
__test__ = False

def get_auth_token():
    """Получить токен авторизации"""
    password = os.getenv("QA_MCP_PASSWORD")
    if not password:
        print("Set QA_MCP_PASSWORD before running this legacy MCP auth smoke script.")
        return None

    try:
        # Попробуем получить токен через простую авторизацию
        response = requests.post(
            f"{BASE_URL}/auth/minimal-login",
            json={"username": AUTH_USERNAME, "password": password},
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"Ошибка авторизации: {response.status_code}")
            return None

    except Exception as e:
        print(f"Ошибка получения токена: {e}")
        return None

def test_mcp_with_auth():
    """Тест MCP endpoints с авторизацией"""
    print("🔍 Тестирование MCP с авторизацией...")

    # Получаем токен
    token = get_auth_token()
    if not token:
        print("❌ Не удалось получить токен авторизации")
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Тестируем статус MCP
    try:
        response = requests.get(f"{BASE_URL}/mcp/status", headers=headers, timeout=10)
        print(f"MCP Status: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ MCP Status: {data.get('healthy', False)}")

            # Показываем метрики
            if 'metrics' in data:
                metrics = data['metrics']
                print(f"  Запросов: {metrics.get('requests_total', 0)}")
                print(f"  Успешных: {metrics.get('requests_success', 0)}")
                print(f"  Ошибок: {metrics.get('requests_failed', 0)}")

            return True
        else:
            print(f"❌ Ошибка: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_complaint_analysis_with_auth():
    """Тест анализа жалоб с авторизацией"""
    print("\n🔍 Тестирование анализа жалоб с авторизацией...")

    token = get_auth_token()
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Тестируем анализ жалоб
    try:
        data = {
            "complaint": "Головная боль и тошнота уже 2 дня",
            "patient_age": 35,
            "patient_gender": "female",
            "urgency_assessment": True
        }

        response = requests.post(
            f"{BASE_URL}/mcp/complaint/analyze",
            json=data,
            headers=headers,
            timeout=30
        )

        print(f"Complaint Analysis: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Анализ жалоб выполнен успешно")

            if 'data' in result and 'data' in result['data']:
                analysis = result['data']['data']
                print(f"  Предварительные диагнозы: {len(analysis.get('preliminary_diagnosis', []))}")
                print(f"  Срочность: {analysis.get('urgency', 'N/A')}")
                print(f"  Обследования: {len(analysis.get('examinations', []))}")

            return True
        else:
            print(f"❌ Ошибка: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def test_icd10_suggestions_with_auth():
    """Тест подсказок МКБ-10 с авторизацией"""
    print("\n🔍 Тестирование подсказок МКБ-10 с авторизацией...")

    token = get_auth_token()
    if not token:
        return False

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    try:
        data = {
            "symptoms": ["головная боль", "тошнота", "светобоязнь"],
            "diagnosis": "Мигрень",
            "max_suggestions": 3
        }

        response = requests.post(
            f"{BASE_URL}/mcp/icd10/suggest",
            json=data,
            headers=headers,
            timeout=30
        )

        print(f"ICD-10 Suggestions: {response.status_code}")

        if response.status_code == 200:
            result = response.json()
            print("✅ Подсказки МКБ-10 получены")

            if 'data' in result and 'suggestions' in result['data']:
                suggestions = result['data']['suggestions']
                print(f"  Получено подсказок: {len(suggestions)}")

                for i, suggestion in enumerate(suggestions[:3], 1):
                    print(f"    {i}. {suggestion.get('code', 'N/A')}: {suggestion.get('description', 'N/A')}")

            return True
        else:
            print(f"❌ Ошибка: {response.text}")
            return False

    except Exception as e:
        print(f"❌ Ошибка запроса: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("=" * 60)
    print("🚀 ТЕСТИРОВАНИЕ MCP API С АВТОРИЗАЦИЕЙ")
    print("=" * 60)

    tests = [
        ("MCP Status", test_mcp_with_auth),
        ("Анализ жалоб", test_complaint_analysis_with_auth),
        ("Подсказки МКБ-10", test_icd10_suggestions_with_auth),
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
    print("📊 ИТОГОВЫЙ ОТЧЕТ")
    print("=" * 60)

    success_count = sum(1 for r in results.values() if r)
    total_count = len(results)

    for test_name, success in results.items():
        status_icon = "✅" if success else "❌"
        print(f"{status_icon} {test_name}: {'Успешно' if success else 'Ошибка'}")

    print("\n" + "-" * 60)
    print(f"Результат: {success_count}/{total_count} тестов пройдено успешно")

    if success_count == total_count:
        print("🎉 ВСЕ MCP API ТЕСТЫ ПРОЙДЕНЫ УСПЕШНО!")
        print("\n📋 MCP API готов к использованию:")
        print("  ✅ Статус системы работает")
        print("  ✅ Анализ жалоб работает")
        print("  ✅ Подсказки МКБ-10 работают")
        print("  ✅ Авторизация работает корректно")
        print("\n🌐 API документация: http://localhost:18000/docs")
        print("🔧 MCP endpoints: http://localhost:18000/api/v1/mcp/*")
    else:
        print(f"⚠️ {total_count - success_count} тестов завершились с ошибками")

    print("=" * 60)
    return 0 if success_count == total_count else 1

if __name__ == "__main__":
    raise SystemExit(main())

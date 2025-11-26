"""
Простые интеграционные тесты для запущенного сервера в CI/CD
"""
import requests
import json


def test_health_endpoint():
    """Тест health endpoint"""
    response = requests.get("http://127.0.0.1:8000/api/v1/health", timeout=30)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "status" in data
    print("✅ Health endpoint работает")


def test_status_endpoint():
    """Тест status endpoint"""
    response = requests.get("http://127.0.0.1:8000/api/v1/status", timeout=30)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    data = response.json()
    assert "status" in data
    print("✅ Status endpoint работает")


def test_openapi_docs():
    """Тест OpenAPI документации"""
    response = requests.get("http://127.0.0.1:8000/docs", timeout=30)
    assert response.status_code == 200, f"Expected 200, got {response.status_code}"
    print("✅ OpenAPI docs доступны")


if __name__ == "__main__":
    try:
        test_health_endpoint()
        test_status_endpoint()
        test_openapi_docs()
        print("✅ Все интеграционные тесты пройдены")
    except Exception as e:
        print(f"❌ Ошибка в интеграционных тестах: {e}")
        raise


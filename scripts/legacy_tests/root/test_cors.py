"""
Тест CORS для MCP API
"""
import os
import sys

import requests

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

BASE_URL = os.getenv("QA_BACKEND_API_BASE_URL", "http://localhost:18000/api/v1")
CORS_ORIGIN = os.getenv("QA_CORS_ORIGIN", "http://localhost:8080")
__test__ = False


def cors_login_payload():
    return {
        "username": os.getenv("QA_CORS_USERNAME", "cors_smoke_user"),
        "password": os.getenv("QA_CORS_PASSWORD", "not-a-real-password"),
    }


def test_cors():
    """Тест CORS настроек"""
    print("🔍 Тестирование CORS настроек...")
    preflight_ok = False
    post_ok = False

    # Тест OPTIONS запроса (preflight)
    try:
        response = requests.options(
            f"{BASE_URL}/auth/minimal-login",
            headers={
                'Origin': CORS_ORIGIN,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'Content-Type'
            }
        )

        print(f"OPTIONS запрос: {response.status_code}")
        print(f"CORS заголовки:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"  {header}: {value}")

        if response.status_code == 200:
            print("✅ CORS preflight работает")
            preflight_ok = True
        else:
            print(f"❌ CORS preflight ошибка: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка CORS теста: {e}")

    # Тест обычного запроса
    try:
        response = requests.post(
            f"{BASE_URL}/auth/minimal-login",
            json=cors_login_payload(),
            headers={
                'Origin': CORS_ORIGIN,
                'Content-Type': 'application/json'
            }
        )

        print(f"\nPOST запрос: {response.status_code}")
        print(f"CORS заголовки:")
        for header, value in response.headers.items():
            if 'access-control' in header.lower():
                print(f"  {header}: {value}")

        if response.status_code in [200, 401]:  # 401 - нормально для неверных данных
            print("✅ CORS запрос работает")
            post_ok = True
        else:
            print(f"❌ CORS запрос ошибка: {response.status_code}")

    except Exception as e:
        print(f"❌ Ошибка CORS запроса: {e}")

    return preflight_ok and post_ok


if __name__ == "__main__":
    raise SystemExit(0 if test_cors() else 1)

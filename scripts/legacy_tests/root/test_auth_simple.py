"""
Простой тест авторизации
"""
import requests
import json
import os

def test_auth():
    """Тест авторизации"""
    print("🔍 Тестирование авторизации...")

    try:
        mcp_password = os.getenv("QA_MCP_PASSWORD")
        if not mcp_password:
            print("Set QA_MCP_PASSWORD before running this legacy auth smoke script.")
            return None
        response = requests.post(
            "http://localhost:18000/api/v1/auth/minimal-login",
            json={"username": os.getenv("QA_MCP_USERNAME", "mcp_test"), "password": mcp_password},
            headers={
                "Content-Type": "application/json",
                "Origin": "http://localhost:8080"
            }
        )

        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Авторизация успешна!")
            print(f"Токен: {data.get('access_token', 'N/A')[:50]}...")
            return data.get('access_token')
        else:
            print(f"❌ Ошибка авторизации: {response.status_code}")
            return None

    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

if __name__ == "__main__":
    token = test_auth()
    if token:
        print(f"\n🎉 Токен получен! Теперь можно тестировать MCP endpoints.")
    else:
        print(f"\n❌ Не удалось получить токен.")

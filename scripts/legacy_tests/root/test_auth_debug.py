"""
Простой тест авторизации с отладкой
"""
import requests
import json
import os

def test_auth_debug():
    """Тест авторизации с отладкой"""
    print("🔍 Тестирование авторизации с отладкой...")

    url = "http://localhost:18000/api/v1/auth/minimal-login"
    mcp_password = os.getenv("QA_MCP_PASSWORD")
    if not mcp_password:
        print("Set QA_MCP_PASSWORD before running this legacy auth smoke script.")
        return None
    data = {
        "username": os.getenv("QA_MCP_USERNAME", "mcp_test"),
        "password": mcp_password
    }
    headers = {
        "Content-Type": "application/json",
        "Origin": "http://localhost:8080"
    }

    print(f"URL: {url}")
    print("Data: <redacted credentials>")
    print(f"Headers: {json.dumps(headers, indent=2)}")

    try:
        response = requests.post(url, json=data, headers=headers, timeout=10)

        print(f"\nResponse Status: {response.status_code}")
        print(f"Response Headers: {dict(response.headers)}")
        print(f"Response Text: {response.text}")

        if response.status_code == 200:
            result = response.json()
            print(f"\n✅ Успешная авторизация!")
            print(f"Token: {result.get('access_token', 'N/A')[:50]}...")
            print(f"User: {result.get('user', {}).get('username', 'N/A')}")
            print(f"Role: {result.get('user', {}).get('role', 'N/A')}")
            return result.get('access_token')
        else:
            print(f"\n❌ Ошибка авторизации: {response.status_code}")
            return None

    except Exception as e:
        print(f"\n❌ Ошибка запроса: {e}")
        return None

if __name__ == "__main__":
    token = test_auth_debug()
    if token:
        print(f"\n🎉 Токен получен: {token[:50]}...")
    else:
        print(f"\n❌ Токен не получен")

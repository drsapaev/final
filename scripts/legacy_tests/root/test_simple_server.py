#!/usr/bin/env python3
"""
Тест простого сервера авторизации
"""
import requests
import json
import os

def test_simple_server():
    """Тест простого сервера авторизации"""
    try:
        admin_password = os.getenv("QA_ADMIN_PASSWORD")
        if not admin_password:
            print("Set QA_ADMIN_PASSWORD before running this legacy auth smoke script.")
            return False
        data = {
            "username": os.getenv("QA_ADMIN_USERNAME", "admin@example.com"),
            "password": admin_password,
            "remember_me": False
        }

        headers = {
            "Content-Type": "application/json"
        }

        print("Sending request to simple auth server with redacted credentials")

        response = requests.post(
            "http://localhost:8001/api/v1/auth/simple",
            json=data,
            headers=headers
        )

        print(f"Simple auth server: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Успешная авторизация!")
            print(f"Access token: {data.get('access_token', 'N/A')[:30]}...")
            print(f"Token type: {data.get('token_type', 'N/A')}")
            print(f"Expires in: {data.get('expires_in', 'N/A')} seconds")
            print(f"User: {data.get('user', {}).get('username', 'N/A')} ({data.get('user', {}).get('role', 'N/A')})")
            return True
        else:
            print(f"Login failed with status: {response.status_code}")
            return False

    except Exception as e:
        print(f"Simple server test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование простого сервера авторизации...")

    print("\n1. Тест простого сервера:")
    login_ok = test_simple_server()

    print(f"\n📊 Результаты:")
    print(f"Simple Server: {'✅' if login_ok else '❌'}")

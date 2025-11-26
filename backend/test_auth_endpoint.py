#!/usr/bin/env python3
"""
Тест auth endpoint напрямую
"""
from fastapi.testclient import TestClient
from app.main import app

def test_auth_endpoint():
    """Тест auth endpoint"""
    print("🔐 ТЕСТ AUTH ENDPOINT")
    print("=" * 30)
    
    client = TestClient(app)
    
    # Тест 1: Health
    print("1. Тестируем health...")
    response = client.get("/api/v1/health")
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Health работает")
    else:
        print(f"   ❌ Health: {response.text}")
    
    # Тест 2: Auth login
    print("\n2. Тестируем auth login...")
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin123"}
    )
    print(f"   Статус: {response.status_code}")
    if response.status_code == 200:
        print("   ✅ Auth login работает")
        data = response.json()
        print(f"   Токен: {data.get('access_token', 'Нет')[:50]}...")
    else:
        print(f"   ❌ Auth login: {response.text}")
    
    # Тест 3: Auth me
    print("\n3. Тестируем auth me...")
    if response.status_code == 200:
        token = response.json().get('access_token')
        headers = {"Authorization": f"Bearer {token}"}
        me_response = client.get("/api/v1/auth/me", headers=headers)
        print(f"   Статус: {me_response.status_code}")
        if me_response.status_code == 200:
            print("   ✅ Auth me работает")
            user_data = me_response.json()
            print(f"   Пользователь: {user_data.get('username', 'Нет')}")
        else:
            print(f"   ❌ Auth me: {me_response.text}")

if __name__ == "__main__":
    test_auth_endpoint()

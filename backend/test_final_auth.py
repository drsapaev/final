#!/usr/bin/env python3
"""
Финальный тест аутентификации
"""
import requests
import json

def test_final_auth():
    """Финальный тест аутентификации"""
    print("🔐 ФИНАЛЬНЫЙ ТЕСТ АУТЕНТИФИКАЦИИ")
    print("=" * 50)
    
    # Тест 1: Health endpoint
    print("1. Тестируем health endpoint...")
    try:
        response = requests.get("http://localhost:18000/api/v1/health", timeout=5)
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health: {data}")
        else:
            print(f"   ❌ Health: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка health: {e}")
    
    # Тест 2: Status endpoint
    print("\n2. Тестируем status endpoint...")
    try:
        response = requests.get("http://localhost:18000/api/v1/status", timeout=5)
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Status: {data}")
        else:
            print(f"   ❌ Status: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка status: {e}")
    
    # Тест 3: Auth login endpoint
    print("\n3. Тестируем auth login endpoint...")
    try:
        response = requests.post(
            "http://localhost:18000/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
            timeout=10
        )
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Auth login работает!")
            print(f"   Токен: {data.get('access_token', 'Нет')[:50]}...")
        else:
            print(f"   ❌ Auth login: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка auth login: {e}")
    
    # Тест 4: Authentication login endpoint
    print("\n4. Тестируем authentication login endpoint...")
    try:
        response = requests.post(
            "http://localhost:18000/api/v1/authentication/login",
            json={"username": "admin", "password": "admin123"},
            timeout=10
        )
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Authentication login работает!")
            print(f"   Токен: {data.get('access_token', 'Нет')[:50]}...")
        else:
            print(f"   ❌ Authentication login: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка authentication login: {e}")

if __name__ == "__main__":
    test_final_auth()

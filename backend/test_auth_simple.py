#!/usr/bin/env python3
"""
Простой тест аутентификации
"""
import requests
import json

def test_auth_simple():
    """Простой тест аутентификации"""
    print("🔐 ПРОСТОЙ ТЕСТ АУТЕНТИФИКАЦИИ")
    print("=" * 40)
    
    # Тест 1: Health endpoint
    print("1. Тестируем health endpoint...")
    try:
        response = requests.get("http://localhost:8000/api/v1/health", timeout=5)
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            print("   ✅ Health работает")
        else:
            print(f"   ❌ Health не работает: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка health: {e}")
    
    # Тест 2: Auth login endpoint
    print("\n2. Тестируем auth login...")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5
        )
        print(f"   Статус: {response.status_code}")
        print(f"   Заголовки: {dict(response.headers)}")
        
        if response.status_code == 200:
            print("   ✅ Login работает")
            try:
                data = response.json()
                print(f"   Токен: {data.get('access_token', 'Нет токена')[:50]}...")
            except:
                print("   ❌ Не удалось распарсить JSON")
        else:
            print(f"   ❌ Login не работает: {response.text[:200]}")
            
    except Exception as e:
        print(f"   ❌ Ошибка login: {e}")
    
    # Тест 3: Authentication login endpoint
    print("\n3. Тестируем authentication login...")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/authentication/login",
            data={"username": "admin", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5
        )
        print(f"   Статус: {response.status_code}")
        
        if response.status_code == 200:
            print("   ✅ Authentication login работает")
        else:
            print(f"   ❌ Authentication login не работает: {response.text[:200]}")
            
    except Exception as e:
        print(f"   ❌ Ошибка authentication login: {e}")

if __name__ == "__main__":
    test_auth_simple()

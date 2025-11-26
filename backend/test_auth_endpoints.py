#!/usr/bin/env python3
"""
Тестирование всех endpoints аутентификации
"""
import requests
import json

def test_auth_endpoints():
    """Тестировать все endpoints аутентификации"""
    base_url = "http://localhost:8000"
    
    # Тестовые данные
    test_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    # Список endpoints для тестирования
    endpoints = [
        "/api/v1/auth/login",
        "/api/v1/authentication/login", 
        "/api/v1/mobile/auth/login"
    ]
    
    print("🔐 Тестирование endpoints аутентификации...")
    
    for endpoint in endpoints:
        print(f"\n📡 Тестирование: {endpoint}")
        
        # Тест с JSON
        try:
            response = requests.post(f"{base_url}{endpoint}", json=test_data)
            print(f"   JSON Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успех! Token: {data.get('access_token', 'N/A')[:20]}...")
                return endpoint, data.get('access_token')
            else:
                print(f"   ❌ Ошибка: {response.text[:100]}...")
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
        
        # Тест с form data
        try:
            response = requests.post(f"{base_url}{endpoint}", data=test_data)
            print(f"   Form Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   ✅ Успех! Token: {data.get('access_token', 'N/A')[:20]}...")
                return endpoint, data.get('access_token')
            else:
                print(f"   ❌ Ошибка: {response.text[:100]}...")
        except Exception as e:
            print(f"   ❌ Исключение: {e}")
    
    return None, None

def test_available_endpoints():
    """Проверить доступные endpoints"""
    print("\n📋 Проверка доступных endpoints...")
    
    try:
        response = requests.get("http://localhost:8000/_routes")
        if response.status_code == 200:
            routes = response.json()
            auth_routes = [route for route in routes if 'login' in route.get('path', '')]
            print(f"   Найдено {len(auth_routes)} endpoints с 'login':")
            for route in auth_routes:
                print(f"   - {route.get('methods', [])} {route.get('path', '')}")
        else:
            print(f"   ❌ Не удалось получить список routes: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

if __name__ == "__main__":
    test_available_endpoints()
    endpoint, token = test_auth_endpoints()
    
    if token:
        print(f"\n🎉 Рабочий endpoint: {endpoint}")
        print(f"   Token: {token[:20]}...")
    else:
        print("\n❌ Ни один endpoint аутентификации не работает")


#!/usr/bin/env python3
"""
Детальное тестирование аутентификации
"""
import requests
import json

def test_authentication_detailed():
    """Детальное тестирование аутентификации"""
    url = "http://localhost:8000/api/v1/authentication/login"
    
    # Тестовые данные
    test_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    print("🔐 Детальное тестирование аутентификации...")
    print(f"   URL: {url}")
    print(f"   Data: {test_data}")
    
    try:
        response = requests.post(url, json=test_data)
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Успех! Token: {data.get('access_token', 'N/A')[:20]}...")
            return data.get('access_token')
        else:
            print(f"   ❌ Ошибка: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        return None

def test_direct_auth():
    """Прямое тестирование аутентификации через OAuth2"""
    url = "http://localhost:8000/api/v1/auth/login"
    
    # Form data для OAuth2
    form_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    print("\n🔐 Тестирование OAuth2 аутентификации...")
    print(f"   URL: {url}")
    print(f"   Form Data: {form_data}")
    
    try:
        response = requests.post(url, data=form_data)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Успех! Token: {data.get('access_token', 'N/A')[:20]}...")
            return data.get('access_token')
        else:
            print(f"   ❌ Ошибка: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Детальное тестирование аутентификации...")
    
    # Тестируем оба метода
    token1 = test_authentication_detailed()
    token2 = test_direct_auth()
    
    if token1 or token2:
        print("\n🎉 Аутентификация работает!")
        if token1:
            print(f"   Authentication endpoint: {token1[:20]}...")
        if token2:
            print(f"   OAuth2 endpoint: {token2[:20]}...")
    else:
        print("\n❌ Аутентификация не работает")


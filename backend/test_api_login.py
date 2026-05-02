#!/usr/bin/env python3
"""
Тестирование API логина
"""
import requests
import json

def test_api_login():
    """Тестировать API логина"""
    url = "http://localhost:18000/api/v1/auth/login"
    
    # Тест с JSON
    print("🔐 Тестирование API логина с JSON...")
    json_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(url, json=json_data)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Успешный вход! Token: {data.get('access_token', 'N/A')[:20]}...")
            return data.get('access_token')
        else:
            print(f"   ❌ Ошибка входа: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Ошибка запроса: {e}")
        return None

def test_api_login_form():
    """Тестировать API логина с form data"""
    url = "http://localhost:18000/api/v1/auth/login"
    
    # Тест с form data
    print("\n🔐 Тестирование API логина с form data...")
    form_data = {
        "username": "admin",
        "password": "admin123"
    }
    
    try:
        response = requests.post(url, data=form_data)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Успешный вход! Token: {data.get('access_token', 'N/A')[:20]}...")
            return data.get('access_token')
        else:
            print(f"   ❌ Ошибка входа: {response.text}")
            return None
            
    except Exception as e:
        print(f"   ❌ Ошибка запроса: {e}")
        return None

if __name__ == "__main__":
    print("🚀 Тестирование API аутентификации...")
    
    # Тестируем оба метода
    token1 = test_api_login()
    token2 = test_api_login_form()
    
    if token1 or token2:
        print("\n🎉 Аутентификация работает!")
    else:
        print("\n❌ Аутентификация не работает")


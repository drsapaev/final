#!/usr/bin/env python3
"""
Тест JSON endpoint авторизации
"""
import requests
import json

def test_json_login():
    """Тест JSON login endpoint"""
    try:
        data = {
            "username": "admin@example.com",
            "password": "admin123",
            "remember_me": False
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"Sending JSON login request with data: {data}")
        
        response = requests.post(
            "http://localhost:8000/api/v1/auth/json-login",
            json=data,
            headers=headers
        )
        
        print(f"JSON login endpoint: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Успешная авторизация!")
            print(f"Access token: {data.get('access_token', 'N/A')[:30]}...")
            print(f"Token type: {data.get('token_type', 'N/A')}")
            print(f"User: {data.get('user', {}).get('username', 'N/A')} ({data.get('user', {}).get('role', 'N/A')})")
            return True
        else:
            print(f"Login failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"JSON login test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование JSON endpoint авторизации...")
    
    print("\n1. Тест /auth/json-login:")
    login_ok = test_json_login()
    
    print(f"\n📊 Результаты:")
    print(f"JSON Login: {'✅' if login_ok else '❌'}")


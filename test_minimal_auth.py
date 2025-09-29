#!/usr/bin/env python3
"""
Тест минимального endpoint авторизации
"""
import requests
import json

def test_minimal_login():
    """Тест минимального login endpoint"""
    try:
        data = {
            "username": "admin@example.com",
            "password": "admin123",
            "remember_me": False
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"Sending minimal login request with data: {data}")
        
        response = requests.post(
            "http://localhost:8000/api/v1/auth/minimal-login",
            json=data,
            headers=headers
        )
        
        print(f"Minimal login endpoint: {response.status_code}")
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
        print(f"Minimal login test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование минимального endpoint авторизации...")
    
    print("\n1. Тест /auth/minimal-login:")
    login_ok = test_minimal_login()
    
    print(f"\n📊 Результаты:")
    print(f"Minimal Login: {'✅' if login_ok else '❌'}")


#!/usr/bin/env python3
"""
Тест простого endpoint авторизации
"""
import requests
import json

def test_simple_login():
    """Тест простого login endpoint"""
    try:
        data = {
            "username": "admin@example.com",
            "password": "admin123",
            "remember_me": False
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"Sending simple login request with data: {data}")
        
        response = requests.post(
            "http://localhost:18000/api/v1/auth/simple-login",
            json=data,
            headers=headers
        )
        
        print(f"Simple login endpoint: {response.status_code}")
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
        print(f"Simple login test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование простого endpoint авторизации...")
    
    print("\n1. Тест /auth/simple-login:")
    login_ok = test_simple_login()
    
    print(f"\n📊 Результаты:")
    print(f"Simple Login: {'✅' if login_ok else '❌'}")


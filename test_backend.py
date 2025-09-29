#!/usr/bin/env python3
"""
Простой тест backend API
"""
import requests
import json

def test_health():
    """Тест health endpoint"""
    try:
        response = requests.get("http://localhost:8000/api/v1/health")
        print(f"Health endpoint: {response.status_code}")
        print(f"Response: {response.text}")
        return response.status_code == 200
    except Exception as e:
        print(f"Health test failed: {e}")
        return False

def test_login():
    """Тест login endpoint"""
    try:
        data = {
            "username": "admin@example.com",
            "password": "admin123",
            "remember_me": False
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"Sending login request with data: {data}")
        
        response = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            json=data,
            headers=headers
        )
        
        print(f"Login endpoint: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            return True
        else:
            print(f"Login failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"Login test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование backend API...")
    
    print("\n1. Тест health endpoint:")
    health_ok = test_health()
    
    print("\n2. Тест login endpoint:")
    login_ok = test_login()
    
    print(f"\n📊 Результаты:")
    print(f"Health: {'✅' if health_ok else '❌'}")
    print(f"Login: {'✅' if login_ok else '❌'}")


#!/usr/bin/env python3
"""
Тест нового endpoint авторизации
"""
import requests
import json

def test_new_login():
    """Тест нового login endpoint"""
    try:
        data = {
            "username": "admin@example.com",
            "password": "admin123",
            "remember_me": False
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        print(f"Sending login request to /authentication/login with data: {data}")
        
        response = requests.post(
            "http://localhost:8000/api/v1/authentication/login",
            json=data,
            headers=headers
        )
        
        print(f"New login endpoint: {response.status_code}")
        print(f"Response: {response.text}")
        
        if response.status_code == 200:
            return True
        else:
            print(f"Login failed with status: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"New login test failed: {e}")
        return False

if __name__ == "__main__":
    print("🧪 Тестирование нового endpoint авторизации...")
    
    print("\n1. Тест /authentication/login:")
    login_ok = test_new_login()
    
    print(f"\n📊 Результаты:")
    print(f"New Login: {'✅' if login_ok else '❌'}")


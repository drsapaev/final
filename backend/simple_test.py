#!/usr/bin/env python3
"""
Простой тест API
"""

import requests
import json

def test_api():
    base_url = "http://localhost:8000"
    
    print("🔍 Тестирование API...")
    
    # 1. Проверка OpenAPI
    try:
        response = requests.get(f"{base_url}/openapi.json", timeout=5)
        if response.status_code == 200:
            print("✅ OpenAPI доступен")
        else:
            print(f"❌ OpenAPI недоступен: {response.status_code}")
    except Exception as e:
        print(f"❌ Ошибка подключения к API: {e}")
        return
    
    # 2. Проверка логина
    try:
        data = {
            "username": "admin",
            "password": "admin123"
        }
        
        response = requests.post(
            f"{base_url}/api/v1/auth/login",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=5
        )
        
        print(f"📊 Статус логина: {response.status_code}")
        print(f"📋 Заголовки: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Логин успешен: {result.get('access_token', '')[:20]}...")
        else:
            print(f"❌ Ошибка логина: {response.text}")
            
    except Exception as e:
        print(f"❌ Ошибка при тестировании логина: {e}")

if __name__ == "__main__":
    test_api()
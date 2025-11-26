#!/usr/bin/env python3
"""
Прямой тест login endpoint для диагностики ошибки 500
"""

import requests
import json

def test_login_endpoint():
    """Тестирование login endpoint"""
    
    url = "http://127.0.0.1:8000/api/v1/authentication/login"
    
    # Тестовые данные
    test_cases = [
        {"username": "admin", "password": "admin"},
        {"username": "doctor", "password": "doctor123"},
        {"username": "registrar", "password": "registrar123"},
    ]
    
    print("🔍 Тестирование login endpoint...")
    print(f"URL: {url}")
    print("-" * 50)
    
    for i, credentials in enumerate(test_cases, 1):
        print(f"\n📝 Тест {i}: {credentials['username']}")
        
        try:
            response = requests.post(
                url,
                json=credentials,
                headers={"Content-Type": "application/json"},
                timeout=10
            )
            
            print(f"Status Code: {response.status_code}")
            print(f"Headers: {dict(response.headers)}")
            
            if response.status_code == 200:
                print("✅ Успешный вход!")
                data = response.json()
                print(f"Response: {json.dumps(data, indent=2, ensure_ascii=False)}")
            else:
                print(f"❌ Ошибка {response.status_code}")
                try:
                    error_data = response.json()
                    print(f"Error: {json.dumps(error_data, indent=2, ensure_ascii=False)}")
                except:
                    print(f"Raw response: {response.text}")
                    
        except requests.exceptions.ConnectionError:
            print("❌ Не удается подключиться к серверу")
            print("Убедитесь, что backend запущен на http://127.0.0.1:8000")
            break
        except Exception as e:
            print(f"❌ Неожиданная ошибка: {e}")

def check_server_health():
    """Проверка доступности сервера"""
    
    health_endpoints = [
        "http://127.0.0.1:8000/health",
        "http://127.0.0.1:8000/docs",
        "http://127.0.0.1:8000/api/v1/health"
    ]
    
    print("🏥 Проверка доступности сервера...")
    print("-" * 50)
    
    for endpoint in health_endpoints:
        try:
            response = requests.get(endpoint, timeout=5)
            print(f"✅ {endpoint} - {response.status_code}")
        except Exception as e:
            print(f"❌ {endpoint} - {e}")

if __name__ == "__main__":
    check_server_health()
    print()
    test_login_endpoint()

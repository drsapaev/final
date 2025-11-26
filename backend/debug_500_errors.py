#!/usr/bin/env python3
"""
Диагностика 500 ошибок в системе
"""
import requests
import json

def debug_500_errors():
    """Диагностика 500 ошибок"""
    print("🔍 ДИАГНОСТИКА 500 ОШИБОК")
    print("=" * 50)
    
    # Получаем токен
    try:
        auth_response = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if auth_response.status_code != 200:
            print(f"❌ Ошибка аутентификации: {auth_response.status_code}")
            return
        
        token = auth_response.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}
        print("✅ Токен получен")
        
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return
    
    # Тестируем проблемные endpoints
    problematic_endpoints = [
        ("/api/v1/analytics/quick-stats", "GET"),
        ("/api/v1/analytics/dashboard", "GET"),
        ("/api/v1/mobile/stats", "GET"),
        ("/api/v1/telegram/bot-status", "GET")
    ]
    
    for endpoint, method in problematic_endpoints:
        print(f"\n🔍 Тестируем {method} {endpoint}")
        try:
            if method == "GET":
                response = requests.get(f"http://localhost:8000{endpoint}", headers=headers, timeout=5)
            else:
                response = requests.post(f"http://localhost:8000{endpoint}", headers=headers, timeout=5)
            
            print(f"   Статус: {response.status_code}")
            if response.status_code == 500:
                print(f"   ❌ 500 Internal Server Error")
                try:
                    error_detail = response.json()
                    print(f"   Детали ошибки: {error_detail}")
                except:
                    print(f"   Текст ответа: {response.text[:200]}...")
            elif response.status_code == 200:
                print(f"   ✅ Работает")
            else:
                print(f"   ⚠️ Статус {response.status_code}")
                
        except Exception as e:
            print(f"   ❌ Ошибка запроса: {e}")

if __name__ == "__main__":
    debug_500_errors()

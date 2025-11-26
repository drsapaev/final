#!/usr/bin/env python3
"""
Тест простых endpoints
"""
import requests
import json

def test_simple_endpoints():
    """Тест простых endpoints"""
    print("🔍 ТЕСТ ПРОСТЫХ ENDPOINTS")
    print("=" * 40)
    
    endpoints = [
        ("GET", "/api/v1/health", "Health"),
        ("GET", "/api/v1/status", "Status"),
        ("GET", "/api/v1/auth/me", "Auth Me (без токена)"),
        ("GET", "/api/v1/authentication/status", "Auth Status"),
        ("GET", "/api/v1/authentication/health", "Auth Health"),
    ]
    
    for method, endpoint, name in endpoints:
        print(f"\n{name} ({method} {endpoint}):")
        try:
            if method == "GET":
                response = requests.get(f"http://localhost:8000{endpoint}", timeout=5)
            else:
                response = requests.post(f"http://localhost:8000{endpoint}", timeout=5)
            
            print(f"   Статус: {response.status_code}")
            if response.status_code == 200:
                print(f"   ✅ {name} работает")
                try:
                    data = response.json()
                    print(f"   Данные: {data}")
                except:
                    print(f"   Ответ: {response.text[:100]}")
            else:
                print(f"   ❌ {name}: {response.text[:100]}")
                
        except Exception as e:
            print(f"   ❌ Ошибка {name}: {e}")

if __name__ == "__main__":
    test_simple_endpoints()

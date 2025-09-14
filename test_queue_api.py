#!/usr/bin/env python3
"""
Простой тест API очереди
"""
import requests
import json

BASE_URL = "http://localhost:8000/api/v1"

def test_health():
    """Тест health endpoint"""
    print("🔍 Тестируем health endpoint...")
    try:
        response = requests.get(f"{BASE_URL}/health")
        print(f"✅ Health: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ Health error: {e}")
        return False

def test_queue_join():
    """Тест вступления в очередь"""
    print("\n🔍 Тестируем вступление в очередь...")
    
    test_data = {
        "token": "test-token-123",
        "patient_name": "Тест Тестович",
        "phone": "+998901234567"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/queue/join",
            json=test_data,
            headers={"Content-Type": "application/json"}
        )
        print(f"✅ Queue join: {response.status_code}")
        print(f"Response: {response.text}")
        return True
    except Exception as e:
        print(f"❌ Queue join error: {e}")
        return False

def test_queue_endpoints():
    """Тест всех endpoints очереди"""
    print("\n🔍 Тестируем все endpoints очереди...")
    
    endpoints = [
        ("GET", "/queue/today?specialist_id=1", "Today queue"),
        ("POST", "/queue/qrcode?day=2025-09-15&specialist_id=1", "QR generation"),
        ("POST", "/queue/open?day=2025-09-15&specialist_id=1", "Open queue"),
    ]
    
    for method, endpoint, name in endpoints:
        try:
            if method == "GET":
                response = requests.get(f"{BASE_URL}{endpoint}")
            else:
                response = requests.post(f"{BASE_URL}{endpoint}")
            
            print(f"✅ {name}: {response.status_code}")
            if response.status_code != 200:
                print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"❌ {name} error: {e}")

if __name__ == "__main__":
    print("🚀 Запуск тестов API очереди...")
    
    # Тест health
    health_ok = test_health()
    
    if health_ok:
        # Тест вступления в очередь
        test_queue_join()
        
        # Тест других endpoints
        test_queue_endpoints()
    
    print("\n✨ Тестирование завершено!")

#!/usr/bin/env python3
"""
Тест простого queue endpoint
"""
import requests
import json

def test_simple_endpoints():
    """Тест простых endpoints"""
    print("🔍 Тестируем простые queue endpoints...")

    # Тест 1: Test endpoint
    print("\n1️⃣ Тестируем /queue/test:")
    try:
        response = requests.get("http://localhost:18000/api/v1/queue/test")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            print(f"   ✅ Response: {response.json()}")
        else:
            print(f"   ❌ Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # Тест 2: Simple join
    print("\n2️⃣ Тестируем /queue/join-simple:")
    test_data = {
        "token": "test-token",
        "patient_name": "Тест Тестович",
        "phone": "+998901234567"
    }

    try:
        response = requests.post(
            "http://localhost:18000/api/v1/queue/join-simple",
            json=test_data
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Success: {result['success']}")
            print(f"   ✅ Message: {result['message']}")
            if result.get('number'):
                print(f"   ✅ Number: {result['number']}")
        else:
            print(f"   ❌ Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # Тест 3: Оригинальный join (для сравнения)
    print("\n3️⃣ Тестируем оригинальный /queue/join:")
    try:
        response = requests.post(
            "http://localhost:18000/api/v1/queue/join",
            json=test_data
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:100]}...")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

if __name__ == "__main__":
    test_simple_endpoints()
    print("\n✨ Тестирование завершено!")

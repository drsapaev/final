#!/usr/bin/env python3
"""
Тест исправленного queue endpoint
"""
import requests
import json

def test_fixed_endpoints():
    """Тест исправленных endpoints"""
    print("🔍 Тестируем исправленные queue endpoints...")

    # Тест 1: Debug endpoint
    print("\n1️⃣ Тестируем /queue/debug:")
    try:
        response = requests.get("http://localhost:18000/api/v1/queue/debug")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"   ✅ Status: {result.get('status')}")
            print(f"   ✅ Database: {result.get('database')}")
            print(f"   ✅ Queue tables: {result.get('queue_tables')}")
            print(f"   ✅ Models: {result.get('models')}")
        else:
            print(f"   ❌ Response: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

    # Тест 2: Fixed join
    print("\n2️⃣ Тестируем /queue/join-fixed:")
    test_data = {
        "token": "test-token-fixed",
        "patient_name": "Исправленный Тест",
        "phone": "+998901234567"
    }

    try:
        response = requests.post(
            "http://localhost:18000/api/v1/queue/join-fixed",
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

if __name__ == "__main__":
    test_fixed_endpoints()
    print("\n✨ Тестирование завершено!")

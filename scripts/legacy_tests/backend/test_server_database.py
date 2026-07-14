#!/usr/bin/env python3
"""
Тест базы данных сервера
"""
import requests
import json

def test_server_database():
    """Тест базы данных сервера"""
    print("🔍 ТЕСТ БАЗЫ ДАННЫХ СЕРВЕРА")
    print("=" * 40)

    # Тест 1: Health endpoint
    print("1. Тестируем health endpoint...")
    try:
        response = requests.get("http://localhost:18000/api/v1/health", timeout=5)
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health: {data}")
        else:
            print(f"   ❌ Health: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка health: {e}")

    # Тест 2: Попробуем получить информацию о базе данных
    print("\n2. Тестируем database info...")
    try:
        # Попробуем endpoint, который может показать информацию о БД
        response = requests.get("http://localhost:18000/api/v1/status", timeout=5)
        print(f"   Статус: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Status: {data}")
        else:
            print(f"   ❌ Status: {response.text}")
    except Exception as e:
        print(f"   ❌ Ошибка status: {e}")

    # Тест 3: Попробуем простой GET запрос к auth
    print("\n3. Тестируем auth me без токена...")
    try:
        response = requests.get("http://localhost:18000/api/v1/auth/me", timeout=5)
        print(f"   Статус: {response.status_code}")
        print(f"   Ответ: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Ошибка auth me: {e}")

if __name__ == "__main__":
    test_server_database()
#!/usr/bin/env python3
"""
Детальная диагностика ошибки API
"""
import requests
import json
import traceback

def test_with_details():
    """Детальный тест с обработкой ошибок"""
    print("🔍 Детальная диагностика API...")
    
    # Тест 1: Health check
    print("\n1️⃣ Тестируем health endpoint:")
    try:
        response = requests.get("http://localhost:8000/api/v1/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
        return False
    
    # Тест 2: Проверка endpoint существования
    print("\n2️⃣ Проверяем существование queue endpoints:")
    try:
        response = requests.get("http://localhost:8000/api/v1/queue/today?specialist_id=1")
        print(f"   /queue/today Status: {response.status_code}")
        if response.status_code != 401:  # Ожидаем 401 (нужна авторизация)
            print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")
    
    # Тест 3: Детальный тест join с обработкой ошибок
    print("\n3️⃣ Детальный тест /queue/join:")
    
    test_data = {
        "token": "test-token-123",
        "patient_name": "Тест Тестович",
        "phone": "+998901234567"
    }
    
    try:
        print(f"   Отправляем данные: {json.dumps(test_data, ensure_ascii=False)}")
        
        response = requests.post(
            "http://localhost:8000/api/v1/queue/join",
            json=test_data,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        
        print(f"   Status: {response.status_code}")
        print(f"   Headers: {dict(response.headers)}")
        
        if response.status_code == 500:
            print(f"   ❌ Internal Server Error")
            print(f"   Response text: {response.text}")
            
            # Попробуем получить детали ошибки
            try:
                error_json = response.json()
                print(f"   Error JSON: {json.dumps(error_json, ensure_ascii=False, indent=2)}")
            except:
                print("   Не удалось распарсить JSON ошибки")
        else:
            print(f"   ✅ Response: {response.text}")
            
    except requests.exceptions.Timeout:
        print("   ❌ Timeout - сервер не отвечает")
    except requests.exceptions.ConnectionError:
        print("   ❌ Connection Error - сервер недоступен")
    except Exception as e:
        print(f"   ❌ Неожиданная ошибка: {e}")
        traceback.print_exc()
    
    # Тест 4: Проверка с минимальными данными
    print("\n4️⃣ Тест с минимальными данными:")
    minimal_data = {
        "token": "test",
        "patient_name": "Test",
        "phone": "+998901234567"
    }
    
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/queue/join",
            json=minimal_data,
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text[:200]}")
    except Exception as e:
        print(f"   ❌ Ошибка: {e}")

if __name__ == "__main__":
    test_with_details()
    print("\n✨ Диагностика завершена!")

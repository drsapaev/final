#!/usr/bin/env python3
"""
Тестирование файловых endpoints
"""
import requests

def test_file_endpoints():
    """Тестирование файловых endpoints"""
    print("🚀 Тестирование файловых endpoints...")
    
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
        print(f"✅ Токен получен")
        
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return
    
    headers = {"Authorization": f"Bearer {token}"}
    
    # Тестируем простой GET endpoint
    print("\n📁 Тестирование GET /api/v1/files/test...")
    try:
        response = requests.get(
            "http://localhost:8000/api/v1/files/test",
            headers=headers,
            timeout=5
        )
        
        print(f"📊 Статус: {response.status_code}")
        print(f"📄 Ответ: {response.text}")
        
        if response.status_code == 200:
            print("✅ GET endpoint работает!")
        else:
            print(f"❌ Ошибка GET: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка GET: {e}")
    
    # Тестируем простой POST endpoint
    print("\n📁 Тестирование POST /api/v1/files/test-upload...")
    try:
        response = requests.post(
            "http://localhost:8000/api/v1/files/test-upload",
            headers=headers,
            timeout=5
        )
        
        print(f"📊 Статус: {response.status_code}")
        print(f"📄 Ответ: {response.text}")
        
        if response.status_code == 200:
            print("✅ POST endpoint работает!")
        else:
            print(f"❌ Ошибка POST: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Ошибка POST: {e}")

if __name__ == "__main__":
    test_file_endpoints()


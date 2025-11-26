#!/usr/bin/env python3
"""
Тестирование упрощенной загрузки файлов
"""
import requests

def test_simple_upload_fixed():
    """Тестирование упрощенной загрузки"""
    print("🚀 Тестирование упрощенной загрузки файлов...")
    
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
    
    # Тестируем упрощенную загрузку
    print("\n📁 Тестирование упрощенной загрузки...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Создаем простой файл
    files = {
        'file': ('test_simple.txt', 'Hello World from simple upload!', 'text/plain')
    }
    
    data = {
        'title': 'Простой тестовый файл'
    }
    
    try:
        print("📤 Отправляем запрос на /api/v1/files/upload-simple...")
        upload_response = requests.post(
            "http://localhost:8000/api/v1/files/upload-simple",
            headers=headers,
            files=files,
            data=data,
            timeout=10
        )
        
        print(f"📊 Статус: {upload_response.status_code}")
        print(f"📄 Ответ: {upload_response.text}")
        
        if upload_response.status_code == 200:
            print("✅ Файл успешно загружен!")
            result = upload_response.json()
            print(f"   Имя файла: {result.get('filename')}")
            print(f"   Размер: {result.get('file_size')} байт")
            print(f"   Хеш: {result.get('file_hash')[:20]}...")
        else:
            print(f"❌ Ошибка: {upload_response.status_code}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Ошибка подключения: {e}")
    except requests.exceptions.Timeout as e:
        print(f"❌ Таймаут: {e}")
    except Exception as e:
        print(f"❌ Другая ошибка: {e}")

if __name__ == "__main__":
    test_simple_upload_fixed()


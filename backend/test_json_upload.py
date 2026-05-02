#!/usr/bin/env python3
"""
Тестирование загрузки файлов через JSON
"""
import requests
import base64

def test_json_upload():
    """Тестирование JSON загрузки"""
    print("🚀 Тестирование загрузки файлов через JSON...")
    
    # Получаем токен
    try:
        auth_response = requests.post(
            "http://localhost:18000/api/v1/auth/login",
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
    
    # Тестируем JSON загрузку
    print("\n📁 Тестирование JSON загрузки...")
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # Создаем тестовый файл
    test_content = "Hello World from JSON upload!"
    encoded_content = base64.b64encode(test_content.encode()).decode()
    
    data = {
        "filename": "test_json.txt",
        "content": encoded_content,
        "title": "JSON тестовый файл",
        "description": "Файл загружен через JSON API"
    }
    
    try:
        print("📤 Отправляем JSON запрос...")
        upload_response = requests.post(
            "http://localhost:18000/api/v1/files/upload-json",
            headers=headers,
            json=data,
            timeout=10
        )
        
        print(f"📊 Статус: {upload_response.status_code}")
        print(f"📄 Ответ: {upload_response.text}")
        
        if upload_response.status_code == 200:
            print("✅ Файл успешно загружен через JSON!")
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
    test_json_upload()


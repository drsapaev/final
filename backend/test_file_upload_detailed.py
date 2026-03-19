#!/usr/bin/env python3
"""
Детальное тестирование загрузки файлов
"""
import requests
import json

def test_file_upload_detailed():
    """Детальное тестирование загрузки файлов"""
    print("🚀 Детальное тестирование загрузки файлов...")
    
    # Получаем токен
    print("\n🔐 Получение токена...")
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
        print(f"✅ Токен получен: {token[:20]}...")
        
    except Exception as e:
        print(f"❌ Ошибка получения токена: {e}")
        return
    
    # Тестируем загрузку файла
    print("\n📁 Тестирование загрузки файла...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Создаем тестовый файл
    test_content = "Это тестовый файл для загрузки"
    files = {
        'file': ('test.txt', test_content, 'text/plain')
    }
    
    data = {
        'title': 'Тестовый файл',
        'description': 'Описание тестового файла',
        'tags': '["test", "upload"]',
        'permission': 'PRIVATE'
    }
    
    try:
        upload_response = requests.post(
            "http://localhost:18000/api/v1/files/upload",
            headers=headers,
            files=files,
            data=data
        )
        
        print(f"📊 Статус загрузки: {upload_response.status_code}")
        print(f"📄 Ответ: {upload_response.text}")
        
        if upload_response.status_code == 200:
            print("✅ Файл успешно загружен!")
            file_data = upload_response.json()
            print(f"   ID файла: {file_data.get('id')}")
            print(f"   Имя файла: {file_data.get('filename')}")
            print(f"   Размер: {file_data.get('file_size')} байт")
        else:
            print(f"❌ Ошибка загрузки: {upload_response.status_code}")
            
    except Exception as e:
        print(f"❌ Исключение при загрузке: {e}")
    
    # Тестируем получение списка файлов
    print("\n📋 Тестирование получения списка файлов...")
    try:
        list_response = requests.get(
            "http://localhost:18000/api/v1/files/",
            headers=headers
        )
        
        print(f"📊 Статус списка: {list_response.status_code}")
        if list_response.status_code == 200:
            files_data = list_response.json()
            print(f"✅ Получен список файлов: {files_data.get('total', 0)} файлов")
        else:
            print(f"❌ Ошибка получения списка: {list_response.text}")
            
    except Exception as e:
        print(f"❌ Исключение при получении списка: {e}")

if __name__ == "__main__":
    test_file_upload_detailed()


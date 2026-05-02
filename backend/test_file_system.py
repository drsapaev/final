#!/usr/bin/env python3
"""
Тестовый скрипт для проверки файловой системы
"""
import requests
import json
import os
from io import BytesIO

# Настройки
BASE_URL = "http://localhost:18000"
TEST_USER = {
    "username": "admin",
    "password": "admin123"
}

def get_auth_token():
    """Получить токен аутентификации"""
    try:
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", data=TEST_USER)
        if response.status_code == 200:
            data = response.json()
            return data.get("access_token")
        else:
            print(f"❌ Ошибка аутентификации: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Ошибка подключения: {e}")
        return None

def test_file_upload(token):
    """Тестировать загрузку файла"""
    print("\n📁 Тестирование загрузки файла...")
    
    # Создаем тестовый файл
    test_content = "This is a test file for file system testing".encode('utf-8')
    test_file = BytesIO(test_content)
    
    files = {
        'file': ('test_file.txt', test_file, 'text/plain')
    }
    
    data = {
        'file_type': 'document',
        'permission': 'private',
        'title': 'Тестовый файл'
    }
    
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/files/upload", files=files, data=data, headers=headers)
        if response.status_code == 200:
            file_data = response.json()
            print(f"✅ Файл загружен: ID={file_data['id']}, размер={file_data['file_size']} байт")
            return file_data['id']
        else:
            print(f"❌ Ошибка загрузки: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return None

def test_file_list(token):
    """Тестировать получение списка файлов"""
    print("\n📋 Тестирование получения списка файлов...")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/files/", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Получен список файлов: {data['total']} файлов")
            return data['files']
        else:
            print(f"❌ Ошибка получения списка: {response.status_code} - {response.text}")
            return []
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return []

def test_file_download(token, file_id):
    """Тестировать скачивание файла"""
    print(f"\n⬇️ Тестирование скачивания файла ID={file_id}...")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/files/{file_id}/download", headers=headers)
        if response.status_code == 200:
            print(f"✅ Файл скачан: {len(response.content)} байт")
            return True
        else:
            print(f"❌ Ошибка скачивания: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_file_stats(token):
    """Тестировать статистику файлов"""
    print("\n📊 Тестирование статистики файлов...")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    try:
        response = requests.get(f"{BASE_URL}/api/v1/files/statistics", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Статистика получена:")
            print(f"   - Всего файлов: {data['total_files']}")
            print(f"   - Общий размер: {data['total_size']} байт")
            print(f"   - По типам: {data['files_by_type']}")
            return True
        else:
            print(f"❌ Ошибка получения статистики: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def test_file_search(token):
    """Тестировать поиск файлов"""
    print("\n🔍 Тестирование поиска файлов...")
    
    headers = {'Authorization': f'Bearer {token}'}
    
    search_data = {
        "query": "тест",
        "file_type": "document",
        "page": 1,
        "size": 10
    }
    
    try:
        response = requests.post(f"{BASE_URL}/api/v1/files/search", json=search_data, headers=headers)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Поиск выполнен: найдено {data['total']} файлов")
            return True
        else:
            print(f"❌ Ошибка поиска: {response.status_code} - {response.text}")
            return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

def main():
    """Основная функция тестирования"""
    print("🚀 Начинаем тестирование файловой системы...")
    
    # Получаем токен аутентификации
    token = get_auth_token()
    if not token:
        print("❌ Не удалось получить токен аутентификации")
        return
    
    print(f"✅ Токен получен: {token[:20]}...")
    
    # Тестируем загрузку файла
    file_id = test_file_upload(token)
    
    # Тестируем получение списка файлов
    files = test_file_list(token)
    
    # Тестируем скачивание файла
    if file_id:
        test_file_download(token, file_id)
    
    # Тестируем статистику
    test_file_stats(token)
    
    # Тестируем поиск
    test_file_search(token)
    
    print("\n🎉 Тестирование файловой системы завершено!")

if __name__ == "__main__":
    main()

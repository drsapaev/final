#!/usr/bin/env python3
"""
Простое тестирование загрузки файлов
"""
import requests
import io

def test_simple_upload():
    """Простое тестирование загрузки"""
    print("🚀 Простое тестирование загрузки...")
    
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
    
    # Простая загрузка
    print("\n📁 Простая загрузка файла...")
    headers = {"Authorization": f"Bearer {token}"}
    
    # Создаем простой файл
    files = {
        'file': ('test.txt', 'Hello World', 'text/plain')
    }
    
    try:
        print("📤 Отправляем запрос...")
        upload_response = requests.post(
            "http://localhost:18000/api/v1/files/upload",
            headers=headers,
            files=files,
            timeout=10
        )
        
        print(f"📊 Статус: {upload_response.status_code}")
        print(f"📄 Ответ: {upload_response.text[:200]}...")
        
        if upload_response.status_code == 200:
            print("✅ Файл загружен!")
        else:
            print(f"❌ Ошибка: {upload_response.status_code}")
            
    except requests.exceptions.ConnectionError as e:
        print(f"❌ Ошибка подключения: {e}")
    except requests.exceptions.Timeout as e:
        print(f"❌ Таймаут: {e}")
    except Exception as e:
        print(f"❌ Другая ошибка: {e}")

if __name__ == "__main__":
    test_simple_upload()


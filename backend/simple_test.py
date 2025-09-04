#!/usr/bin/env python3
"""
Простой тест логина
"""

import requests
import time

def test_login():
    """Простой тест логина"""
    # Ждем запуска сервера
    time.sleep(2)
    
    try:
        print("Тестируем логин...")
        response = requests.post(
            'http://localhost:8000/api/v1/auth/login',
            data={
                'username': 'admin',
                'password': 'admin123',
                'grant_type': 'password'
            },
            headers={'Content-Type': 'application/x-www-form-urlencoded'}
        )
        
        print(f"Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print("✅ Логин успешен!")
            print(f"Token: {data.get('access_token', 'N/A')[:30]}...")
            return True
        else:
            print(f"❌ Ошибка: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Сервер не доступен")
        return False
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False

if __name__ == "__main__":
    success = test_login()
    if success:
        print("\n🎉 Аутентификация работает!")
    else:
        print("\n❌ Проблема с аутентификацией")

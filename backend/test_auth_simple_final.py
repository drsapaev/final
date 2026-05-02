#!/usr/bin/env python3
"""
Простой тест аутентификации
"""
import requests
import time

BASE_URL = "http://localhost:18000/api/v1"

def test_auth_simple():
    print("🔐 ПРОСТОЙ ТЕСТ АУТЕНТИФИКАЦИИ")
    print("==============================")
    
    # Тестовые пользователи
    test_users = [
        {"username": "admin", "password": "admin123"},
        {"username": "registrar", "password": "registrar123"},
        {"username": "lab", "password": "lab123"},
        {"username": "doctor", "password": "doctor123"},
        {"username": "cashier", "password": "cashier123"},
        {"username": "cardio", "password": "cardio123"},
        {"username": "derma", "password": "derma123"},
        {"username": "dentist", "password": "dentist123"}
    ]
    
    success_count = 0
    total_count = len(test_users)
    
    for user_data in test_users:
        username = user_data["username"]
        password = user_data["password"]
        
        print(f"\n🔑 Тестируем {username}...")
        
        try:
            # Пробуем логин
            login_data = {"username": username, "password": password}
            response = requests.post(
                f"{BASE_URL}/auth/login", 
                data=login_data,
                timeout=10
            )
            
            if response.status_code == 200:
                token = response.json().get("access_token")
                print(f"   ✅ Логин успешен, токен: {token[:20]}...")
                success_count += 1
            else:
                print(f"   ❌ Ошибка логина: {response.status_code}")
                print(f"   Детали: {response.text}")
                
        except requests.exceptions.Timeout:
            print(f"   ⏰ Таймаут при логине {username}")
        except requests.exceptions.ConnectionError as e:
            print(f"   🔌 Ошибка подключения: {e}")
        except Exception as e:
            print(f"   ❌ Неожиданная ошибка: {e}")
    
    print(f"\n📊 ИТОГИ:")
    print(f"   ✅ Успешных логинов: {success_count}/{total_count}")
    print(f"   ❌ Неудачных логинов: {total_count - success_count}/{total_count}")
    print(f"   📈 Процент успеха: {(success_count/total_count)*100:.1f}%")
    
    if success_count == total_count:
        print(f"\n🎉 ВСЕ ПОЛЬЗОВАТЕЛИ МОГУТ ЛОГИНИТЬСЯ!")
    elif success_count > 0:
        print(f"\n⚠️ ЧАСТИЧНЫЙ УСПЕХ - НЕКОТОРЫЕ ПОЛЬЗОВАТЕЛИ МОГУТ ЛОГИНИТЬСЯ")
    else:
        print(f"\n❌ КРИТИЧЕСКАЯ ПРОБЛЕМА - НИКТО НЕ МОЖЕТ ЛОГИНИТЬСЯ")

if __name__ == "__main__":
    test_auth_simple()

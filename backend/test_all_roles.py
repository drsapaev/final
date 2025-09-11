#!/usr/bin/env python3
"""
Тестирование всех ролей системы
"""
import requests
import json

def test_role_login(username, password, expected_role):
    """Тестировать логин для конкретной роли"""
    print(f"\n🔐 Тестируем роль: {username}")
    
    try:
        # OAuth2 логин
        response = requests.post(
            "http://localhost:8000/api/v1/auth/login",
            data={
                "username": username,
                "password": password
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code == 200:
            data = response.json()
            token = data.get("access_token")
            print(f"   ✅ Логин успешен")
            print(f"   🎫 Token: {token[:20]}...")
            
            # Проверяем профиль
            profile_response = requests.get(
                "http://localhost:8000/api/v1/auth/me",
                headers={"Authorization": f"Bearer {token}"}
            )
            
            if profile_response.status_code == 200:
                profile = profile_response.json()
                actual_role = profile.get("role")
                print(f"   👤 Роль: {actual_role}")
                
                if actual_role == expected_role:
                    print(f"   ✅ Роль корректна")
                    return True
                else:
                    print(f"   ❌ Неправильная роль: ожидалось {expected_role}, получено {actual_role}")
                    return False
            else:
                print(f"   ❌ Ошибка получения профиля: {profile_response.status_code}")
                return False
        else:
            print(f"   ❌ Ошибка логина: {response.status_code}")
            print(f"   📄 Ответ: {response.text}")
            return False
            
    except Exception as e:
        print(f"   ❌ Исключение: {e}")
        return False

def main():
    """Тестировать все роли"""
    print("🚀 Тестирование всех ролей системы...")
    
    # Список ролей для тестирования
    roles = [
        ("admin", "admin123", "Admin"),
        ("registrar", "registrar123", "Registrar"),
        ("lab", "lab123", "Lab"),
        ("doctor", "doctor123", "Doctor"),
        ("cashier", "cashier123", "Cashier"),
        ("cardio", "cardio123", "cardio"),
        ("derma", "derma123", "derma"),
        ("dentist", "dentist123", "dentist")
    ]
    
    success_count = 0
    total_count = len(roles)
    
    for username, password, expected_role in roles:
        if test_role_login(username, password, expected_role):
            success_count += 1
    
    print(f"\n📊 РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ:")
    print(f"   ✅ Успешно: {success_count}/{total_count}")
    print(f"   ❌ Ошибок: {total_count - success_count}/{total_count}")
    
    if success_count == total_count:
        print(f"\n🎉 ВСЕ РОЛИ РАБОТАЮТ КОРРЕКТНО!")
        return True
    else:
        print(f"\n⚠️  ЕСТЬ ПРОБЛЕМЫ С НЕКОТОРЫМИ РОЛЯМИ")
        return False

if __name__ == "__main__":
    main()

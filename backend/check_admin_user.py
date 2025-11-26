#!/usr/bin/env python3
"""
Проверка пользователя admin
"""

import sqlite3

def check_admin_user():
    """Проверка пользователя admin в базе данных"""
    
    try:
        conn = sqlite3.connect('clinic.db')
        cursor = conn.cursor()
        
        # Ищем пользователя admin
        cursor.execute("SELECT id, username, password, role FROM users WHERE username = 'admin'")
        admin_user = cursor.fetchone()
        
        if admin_user:
            print(f"✅ Пользователь admin найден:")
            print(f"  - ID: {admin_user[0]}")
            print(f"  - Username: {admin_user[1]}")
            print(f"  - Password hash: {admin_user[2][:20]}...")
            print(f"  - Role: {admin_user[3]}")
        else:
            print("❌ Пользователь admin не найден")
            
            # Покажем всех пользователей
            cursor.execute("SELECT username, role FROM users")
            all_users = cursor.fetchall()
            print(f"\n📋 Все пользователи в системе ({len(all_users)}):")
            for user in all_users:
                print(f"  - {user[0]} ({user[1]})")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def test_admin_passwords():
    """Тестирование различных паролей для admin"""
    
    import requests
    
    url = "http://127.0.0.1:8000/api/v1/authentication/login"
    
    # Возможные пароли для admin
    passwords = [
        "admin123",
        "password",
        "123456",
        "admin12",
        "clinic123",
        "superadmin"
    ]
    
    print(f"\n🔐 Тестирование паролей для admin...")
    print("-" * 50)
    
    for password in passwords:
        try:
            response = requests.post(
                url,
                json={"username": "admin", "password": password},
                timeout=5
            )
            
            if response.status_code == 200:
                print(f"✅ Пароль '{password}' - РАБОТАЕТ!")
                data = response.json()
                user = data.get('user', {})
                print(f"   Роль: {user.get('role')}")
                return password
            else:
                print(f"❌ Пароль '{password}' - не подходит ({response.status_code})")
                
        except Exception as e:
            print(f"❌ Пароль '{password}' - ошибка: {e}")
    
    print("\n❌ Ни один из паролей не подошел")
    return None

if __name__ == "__main__":
    check_admin_user()
    test_admin_passwords()

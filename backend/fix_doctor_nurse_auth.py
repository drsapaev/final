#!/usr/bin/env python3
"""
ИСПРАВЛЕНИЕ ПРОБЛЕМ С ПОДКЛЮЧЕНИЕМ ДЛЯ DOCTOR И NURSE
"""
import sqlite3
import os
from argon2 import PasswordHasher

def fix_doctor_nurse_auth():
    print("🔧 ИСПРАВЛЕНИЕ ПОДКЛЮЧЕНИЯ ДЛЯ DOCTOR И NURSE")
    print("=" * 60)
    
    db_path = 'clinic.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Проверяем пользователей doctor и nurse
        print("1. Проверяем пользователей doctor и nurse...")
        
        users_to_fix = [
            {"username": "doctor", "password": "doctor123", "role": "doctor"},
            {"username": "nurse", "password": "nurse123", "role": "nurse"}
        ]
        
        for user in users_to_fix:
            print(f"\n   🔍 Проверяем {user['username']}...")
            
            # Проверяем существование пользователя
            cursor.execute("SELECT id, username, hashed_password, role, is_active FROM users WHERE username = ?;", (user['username'],))
            user_data = cursor.fetchone()
            
            if user_data:
                user_id, username, hashed_password, role, is_active = user_data
                print(f"      ✅ Пользователь {username} найден (ID: {user_id})")
                print(f"      📊 Роль: {role}, Активен: {is_active}")
                
                # Проверяем пароль
                ph = PasswordHasher()
                try:
                    ph.verify(hashed_password, user['password'])
                    print(f"      ✅ Пароль {username} корректный")
                except Exception as e:
                    print(f"      ❌ Пароль {username} некорректный: {e}")
                    
                    # Пересоздаем хеш пароля
                    print(f"      🔄 Пересоздаем хеш пароля для {username}...")
                    new_hash = ph.hash(user['password'])
                    cursor.execute("UPDATE users SET hashed_password = ? WHERE username = ?;", (new_hash, username))
                    print(f"      ✅ Хеш пароля для {username} обновлен")
                
                # Проверяем и исправляем активность
                if not is_active:
                    print(f"      🔄 Активируем {username}...")
                    cursor.execute("UPDATE users SET is_active = 1 WHERE username = ?;", (username,))
                    print(f"      ✅ {username} активирован")
                
                # Проверяем роль
                if role.lower() != user['role']:
                    print(f"      🔄 Исправляем роль для {username}...")
                    cursor.execute("UPDATE users SET role = ? WHERE username = ?;", (user['role'], username))
                    print(f"      ✅ Роль для {username} исправлена на {user['role']}")
                    
            else:
                print(f"      ❌ Пользователь {user['username']} не найден")
                
                # Создаем пользователя
                print(f"      🔄 Создаем пользователя {user['username']}...")
                ph = PasswordHasher()
                hashed_password = ph.hash(user['password'])
                
                cursor.execute("""
                    INSERT INTO users (username, email, hashed_password, full_name, role, is_active)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    user['username'],
                    f"{user['username']}@clinic.com",
                    hashed_password,
                    f"{user['role'].title()} системы",
                    user['role'],
                    True
                ))
                print(f"      ✅ Пользователь {user['username']} создан")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Исправление подключения для doctor и nurse завершено!")
        
        # 2. Тестируем аутентификацию
        print("\n🧪 Тестируем аутентификацию doctor и nurse...")
        test_doctor_nurse_auth()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def test_doctor_nurse_auth():
    """Тестирование аутентификации doctor и nurse"""
    import requests
    
    users_to_test = [
        {"username": "doctor", "password": "doctor123"},
        {"username": "nurse", "password": "nurse123"}
    ]
    
    for user in users_to_test:
        print(f"\n   🧪 Тестируем {user['username']}...")
        
        try:
            response = requests.post(
                "http://localhost:8000/api/v1/auth/login",
                data={"username": user['username'], "password": user['password']},
                timeout=10
            )
            
            if response.status_code == 200:
                token = response.json()["access_token"]
                print(f"      ✅ {user['username']} успешно вошел в систему")
                print(f"      🔑 Токен получен: {token[:20]}...")
            else:
                print(f"      ❌ Ошибка входа {user['username']}: {response.status_code}")
                print(f"      📝 Ответ: {response.text[:100]}...")
                
        except Exception as e:
            print(f"      ❌ Ошибка подключения для {user['username']}: {e}")

if __name__ == "__main__":
    fix_doctor_nurse_auth()

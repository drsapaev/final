#!/usr/bin/env python3
"""
ИСПРАВЛЕНИЕ ПРОБЛЕМЫ С АУТЕНТИФИКАЦИЕЙ ADMIN
"""
import sqlite3
import os
from argon2 import PasswordHasher

def fix_admin_auth():
    print("🔧 ИСПРАВЛЕНИЕ АУТЕНТИФИКАЦИИ ADMIN")
    print("=" * 50)
    
    db_path = 'clinic.db'
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 1. Проверяем существование пользователя admin
        print("1. Проверяем пользователя admin...")
        cursor.execute("SELECT id, username, hashed_password FROM users WHERE username = 'admin';")
        admin_user = cursor.fetchone()
        
        if admin_user:
            print(f"   ✅ Пользователь admin найден (ID: {admin_user[0]})")
            
            # 2. Проверяем пароль
            print("2. Проверяем пароль admin...")
            ph = PasswordHasher()
            try:
                ph.verify(admin_user[2], "admin123")
                print("   ✅ Пароль admin корректный")
            except Exception as e:
                print(f"   ❌ Пароль admin некорректный: {e}")
                
                # Пересоздаем хеш пароля
                print("   🔄 Пересоздаем хеш пароля...")
                new_hash = ph.hash("admin123")
                cursor.execute("UPDATE users SET hashed_password = ? WHERE username = 'admin';", (new_hash,))
                print("   ✅ Хеш пароля обновлен")
        else:
            print("   ❌ Пользователь admin не найден")
            
            # Создаем пользователя admin
            print("   🔄 Создаем пользователя admin...")
            ph = PasswordHasher()
            hashed_password = ph.hash("admin123")
            
            cursor.execute("""
                INSERT INTO users (username, email, hashed_password, full_name, role, is_active, is_verified)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                "admin",
                "admin@clinic.com", 
                hashed_password,
                "Администратор системы",
                "admin",
                True,
                True
            ))
            print("   ✅ Пользователь admin создан")
        
        # 3. Проверяем роль admin
        print("3. Проверяем роль admin...")
        cursor.execute("SELECT role FROM users WHERE username = 'admin';")
        role = cursor.fetchone()[0]
        print(f"   📊 Роль admin: {role}")
        
        # 4. Проверяем активность
        print("4. Проверяем активность admin...")
        cursor.execute("SELECT is_active, is_verified FROM users WHERE username = 'admin';")
        active, verified = cursor.fetchone()
        print(f"   📊 Активен: {active}, Верифицирован: {verified}")
        
        # 5. Обновляем статус если нужно
        if not active or not verified:
            print("   🔄 Активируем admin...")
            cursor.execute("UPDATE users SET is_active = 1, is_verified = 1 WHERE username = 'admin';")
            print("   ✅ Admin активирован")
        
        conn.commit()
        conn.close()
        
        print("\n✅ Исправление аутентификации admin завершено!")
        
        # 6. Тестируем аутентификацию
        print("\n🧪 Тестируем аутентификацию admin...")
        test_admin_auth()
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")

def test_admin_auth():
    """Тестирование аутентификации admin"""
    import requests
    
    try:
        response = requests.post(
            "http://localhost:18000/api/v1/auth/login",
            data={"username": "admin", "password": "admin123"},
            timeout=10
        )
        
        if response.status_code == 200:
            token = response.json()["access_token"]
            print(f"   ✅ Admin успешно вошел в систему")
            print(f"   🔑 Токен получен: {token[:20]}...")
            return token
        else:
            print(f"   ❌ Ошибка входа admin: {response.status_code}")
            print(f"   📝 Ответ: {response.text[:100]}...")
            return None
            
    except Exception as e:
        print(f"   ❌ Ошибка подключения: {e}")
        return None

if __name__ == "__main__":
    fix_admin_auth()

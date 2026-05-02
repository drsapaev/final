#!/usr/bin/env python3
"""
Прямое тестирование аутентификации
"""
import sqlite3
import hashlib
import secrets

def test_auth():
    """Тестировать аутентификацию напрямую"""
    conn = sqlite3.connect("clinic.db")
    cursor = conn.cursor()
    
    try:
        # Получаем данные админа
        cursor.execute("SELECT id, username, hashed_password FROM users WHERE username = 'admin'")
        admin = cursor.fetchone()
        
        if not admin:
            print("❌ Админ не найден")
            return False
        
        print(f"✅ Админ найден: ID={admin[0]}, Username={admin[1]}")
        print(f"   Password hash: {admin[2][:20]}...")
        
        # Проверяем, что пароль не пустой
        if not admin[2]:
            print("❌ Пароль не установлен")
            return False
        
        print(f"   Stored hash: {admin[2]}")
        print(f"   Hash length: {len(admin[2])}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    test_auth()

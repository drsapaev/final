#!/usr/bin/env python3
"""
Тестирование верификации пароля
"""
import sys
sys.path.append('.')

from app.crud.user import verify_password
import sqlite3

def test_password_verification():
    """Тестировать верификацию пароля"""
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
        print(f"   Stored hash: {admin[2]}")
        
        # Тестируем верификацию пароля
        password = "admin123"
        stored_hash = admin[2]
        
        print(f"   Testing password: {password}")
        print(f"   Stored hash: {stored_hash}")
        
        try:
            result = verify_password(password, stored_hash)
            print(f"   Verification result: {result}")
            return result
        except Exception as e:
            print(f"   Verification error: {e}")
            return False
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    test_password_verification()


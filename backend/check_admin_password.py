#!/usr/bin/env python3
"""
Проверить пароль admin
"""
import sqlite3
from passlib.context import CryptContext

def check_admin_password():
    """Проверить пароль admin"""
    conn = sqlite3.connect('clinic.db')
    cursor = conn.cursor()
    
    try:
        # Получаем данные admin
        cursor.execute("SELECT id, username, hashed_password FROM users WHERE username = 'admin'")
        admin = cursor.fetchone()
        
        if not admin:
            print("❌ Пользователь admin не найден")
            return
        
        print(f"✅ Пользователь admin найден:")
        print(f"   ID: {admin[0]}")
        print(f"   Username: {admin[1]}")
        print(f"   Password hash: {admin[2]}")
        
        # Проверяем пароль
        pwd_context = CryptContext(schemes=["argon2", "bcrypt"], deprecated="auto")
        
        test_passwords = ["admin123", "admin", "password", "123456"]
        
        for password in test_passwords:
            try:
                if pwd_context.verify(password, admin[2]):
                    print(f"✅ Пароль '{password}' ПРАВИЛЬНЫЙ")
                    return
                else:
                    print(f"❌ Пароль '{password}' неправильный")
            except Exception as e:
                print(f"❌ Ошибка проверки пароля '{password}': {e}")
        
        print("\n🔍 Попробуем создать новый пароль для admin...")
        new_password = "admin123"
        new_hash = pwd_context.hash(new_password)
        
        cursor.execute("UPDATE users SET hashed_password = ? WHERE username = 'admin'", (new_hash,))
        conn.commit()
        
        print(f"✅ Пароль admin обновлен на '{new_password}'")
        print(f"   Новый хеш: {new_hash[:50]}...")
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
    finally:
        conn.close()

if __name__ == "__main__":
    check_admin_password()


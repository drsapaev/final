#!/usr/bin/env python3
"""
Создание администратора для тестирования
"""
import sqlite3
import hashlib
import os
import secrets


def _required_admin_password() -> str:
    password = os.getenv("ADMIN_PASSWORD", "").strip()
    if not password:
        raise RuntimeError("Set ADMIN_PASSWORD before creating the admin user.")
    return password


def create_admin():
    """Создать администратора"""
    conn = sqlite3.connect("clinic.db")
    cursor = conn.cursor()
    
    try:
        # Проверяем, есть ли уже админ
        cursor.execute("SELECT id FROM users WHERE username = 'admin'")
        if cursor.fetchone():
            print("✅ Администратор уже существует")
            return True
        
        # Создаем хеш пароля
        password = _required_admin_password()
        salt = secrets.token_hex(16)
        password_hash = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt.encode('utf-8'), 100000)
        password_hash_hex = password_hash.hex()
        
        # Создаем админа
        cursor.execute("""
            INSERT INTO users (username, email, full_name, password_hash, salt, role, is_active, is_superuser)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "admin",
            "admin@clinic.com",
            "Системный администратор",
            password_hash_hex,
            salt,
            "admin",
            1,
            1
        ))
        
        conn.commit()
        print("✅ Администратор создан: admin")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    create_admin()

